# analytics/event_classifier.py
"""
事件分类模块
使用策略模式对事件进行类型分类，支持 NLP 投票、基础关键词匹配、LLM 三种策略。
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Set

from core.models import EventType, EventInfoEnhanced
from core.config_manager import ConfigManager

from analytics.llm_classifier import LLM_AVAILABLE as LLM_LIB_AVAILABLE, LLMEventClassifier


# ------------------------------------------------------------------
#  Strategy Interface
# ------------------------------------------------------------------

class ClassificationStrategy(ABC):
    """分类策略抽象基类"""

    @abstractmethod
    def classify(self, events: List[EventInfoEnhanced],
                 event_keywords: Dict[EventType, List[str]],
                 tokenizer: Optional[Callable[[str], set]] = None) -> None:
        """原地分类事件（修改 event.event_type / event.confidence）"""
        ...


# ------------------------------------------------------------------
#  Basic
# ------------------------------------------------------------------

class BasicClassificationStrategy(ClassificationStrategy):
    """基础关键词匹配分类"""

    def __init__(self, config_manager: ConfigManager):
        self._config = config_manager

    def classify(self, events: List[EventInfoEnhanced],
                 event_keywords: Dict[EventType, List[str]],
                 tokenizer=None) -> None:
        for event in events:
            text = " ".join(t.title for t in event.topics)
            scores: Dict[EventType, int] = {}
            for et, kws in event_keywords.items():
                scores[et] = sum(1 for kw in kws if kw in text)
            if scores:
                best, mx = max(scores.items(), key=lambda x: x[1])
                event.event_type = best.cn
                total = sum(scores.values())
                event.confidence = mx / total if total > 0 else 0.0
            else:
                event.event_type = "其他"
                event.confidence = 0.0


# ------------------------------------------------------------------
#  NLP (voting + text matching)
# ------------------------------------------------------------------

class NLPClassificationStrategy(ClassificationStrategy):
    """NLP 投票 + 文本匹配分类"""

    def __init__(self, config_manager: ConfigManager):
        self._config = config_manager

    def classify(self, events: List[EventInfoEnhanced],
                 event_keywords: Dict[EventType, List[str]],
                 tokenizer: Optional[Callable[[str], set]] = None) -> None:
        weights = self._config.get_type_weight_coefficients()
        strong_excl = self._config.get_politics_strong_exclusion()
        soft_excl = self._config.get_politics_soft_exclusion()

        for event in events:
            # ---- 话题级投票 ----
            votes: Dict = defaultdict(float)
            for topic in event.topics:
                votes[topic.event_type] += 1 + topic.heat_score * 0.01

            # ---- 合并文本关键词匹配 ----
            parts: List[str] = []
            for t in event.topics:
                parts.append(t.title)
                parts.extend(t.keywords)
            text = " ".join(parts)

            has_strong = any(w in text for w in strong_excl)
            has_soft = any(w in text for w in soft_excl)

            text_scores: Dict[EventType, float] = {}
            for et, kws in event_keywords.items():
                s = 0.0
                words: Set[str] = tokenizer(text) if tokenizer else set()
                for kw in kws:
                    if kw in words or kw in text:
                        s += 1 + len(kw) / 2.0
                if et.value in weights:
                    s *= weights[et.value]
                if et == EventType.POLITICS:
                    if has_strong:
                        s = 0
                    elif has_soft:
                        s *= 0.3
                text_scores[et] = s / max(len(event.topics), 1)

            # ---- 综合 ----
            final: Dict = {}
            for et in set(votes.keys()) | set(text_scores.keys()):
                final[et] = votes.get(et, 0) * 3 + text_scores.get(et, 0)

            if final:
                mx = max(final.values())
                best = max(final, key=final.get)
                total = sum(final.values())
                event.event_type = best.cn if isinstance(best, EventType) else str(best)
                event.confidence = min(mx / total + 0.3, 1.0) if total > 0 else 0.0
            else:
                event.event_type = "其他"
                event.confidence = 0.0


# ------------------------------------------------------------------
#  LLM
# ------------------------------------------------------------------

class LLMClassificationStrategy(ClassificationStrategy):
    """LLM 模型分类（Qwen2.5）"""

    def __init__(self, config_manager: ConfigManager):
        self._config = config_manager
        self._classifier: Optional[LLMEventClassifier] = None

    def classify(self, events: List[EventInfoEnhanced],
                 event_keywords: Dict[EventType, List[str]],
                 tokenizer=None) -> None:
        try:
            clf = self._get_classifier()
            if clf is None:
                raise RuntimeError("LLM 分类器不可用")

            results = clf.classify_events(events)
            applied = 0
            for event in events:
                if event.event_id in results:
                    cat, conf = results[event.event_id]
                    event.event_type = cat
                    event.confidence = conf
                    applied += 1
            print(f"  ✓ LLM 分类完成，已分类 {applied}/{len(events)} 个事件")
        except Exception as e:
            print(f"  ⚠ LLM 分类失败: {e}，降级为话题投票")
            raise  # 交由 EventClassifier 的 fallback 处理

    def _get_classifier(self) -> Optional[LLMEventClassifier]:
        if self._classifier is None:
            from analytics.llm_classifier import get_classifier
            self._classifier = get_classifier()
            if self._classifier is None:
                self._classifier = LLMEventClassifier()
        return self._classifier if self._classifier.enabled else None


# ------------------------------------------------------------------
#  Classifier (strategy holder with fallback)
# ------------------------------------------------------------------

class EventClassifier:
    """事件分类器：持有主策略和备用策略，自动降级"""

    def __init__(self, strategy: ClassificationStrategy,
                 fallback: Optional[ClassificationStrategy] = None):
        self._strategy = strategy
        self._fallback = fallback

    def classify(self, events: List[EventInfoEnhanced],
                 event_keywords: Dict[EventType, List[str]],
                 tokenizer: Optional[Callable[[str], set]] = None) -> None:
        try:
            self._strategy.classify(events, event_keywords, tokenizer)
        except Exception as e:
            if self._fallback:
                print(f"  ↓ 降级到备用策略")
                self._fallback.classify(events, event_keywords, tokenizer)
            else:
                raise

    @staticmethod
    def propagate_to_topics(events: List[EventInfoEnhanced]):
        """将事件级分类结果回传到所属话题"""
        for event in events:
            for topic in event.topics:
                topic.event_type = event.event_type
