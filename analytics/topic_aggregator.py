# analytics/topic_aggregator.py
"""
话题聚合模块
负责：标题标准化去重 → 分词缓存 → 话题聚合 → 关键词提取 → 热度计算
"""

import re
from typing import Dict, List
from collections import defaultdict, Counter

from core.models import (
    HotSearchInfo, TrendingTopicEnhanced, KeywordInfoEnhanced, EventType,
)
from core.config_manager import ConfigManager

try:
    import jieba
    import jieba.analyse
    from sklearn.feature_extraction.text import TfidfVectorizer
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False


class TopicAggregator:
    """话题聚合器"""

    def __init__(self, config_manager: ConfigManager, use_nlp: bool = True):
        self.config_manager = config_manager
        self.use_nlp = use_nlp and NLP_AVAILABLE
        self.EVENT_KEYWORDS: Dict[EventType, List[str]] = self._load_event_keywords()
        self.STOP_WORDS = config_manager.get_stop_words()
        self._title_words_cache: Dict[str, set] = {}
        self._hotsearch_list: List[HotSearchInfo] = []

    def _load_event_keywords(self) -> Dict[EventType, List[str]]:
        raw = self.config_manager.get_event_keywords()
        result: Dict[EventType, List[str]] = {}
        for key, data in raw.items():
            try:
                et = EventType(key)
                if isinstance(data, dict):
                    kws = data.get("keywords", [])
                elif isinstance(data, list):
                    kws = data
                else:
                    continue
                result[et] = [str(k) if k is not None else "" for k in kws]
            except ValueError:
                continue
        print(f"成功加载事件关键词配置: {len(result)} 种事件类型" if result else "未加载到事件关键词配置，使用空字典")
        return result

    # ------------------------------------------------------------------
    #  Tokenization
    # ------------------------------------------------------------------

    def init_token_cache(self, hotsearch_list: List[HotSearchInfo]):
        """预计算所有标题的分词缓存"""
        self._title_words_cache.clear()
        _cut = (lambda t: set(jieba.cut(t))) if self.use_nlp else (lambda t: set(re.findall(r'[\w]+', t)))
        for hs in hotsearch_list:
            if hs.title not in self._title_words_cache:
                self._title_words_cache[hs.title] = _cut(hs.title)

    def tokenize(self, text: str) -> set:
        cached = self._title_words_cache.get(text)
        if cached is not None:
            return cached
        return set(jieba.cut(text)) if self.use_nlp else set(re.findall(r'[\w]+', text))

    def calculate_similarity(self, title1: str, title2: str) -> float:
        w1, w2 = self.tokenize(title1), self.tokenize(title2)
        if not w1 or not w2:
            return 0.0
        inter, union = len(w1 & w2), len(w1 | w2)
        return inter / union if union > 0 else 0.0

    def is_same_event(self, t1_title: str, t2_title: str) -> bool:
        if self.calculate_similarity(t1_title, t2_title) >= 0.55:
            return True
        k1, k2 = self.tokenize(t1_title), self.tokenize(t2_title)
        return len(k1 & k2) >= 3

    # ------------------------------------------------------------------
    #  Title Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_title(title: str) -> str:
        return re.sub(r'[""\u201c\u201d\'\'\u2018\u2019「」『』【】\[\]（）()\u3000]', '', title)

    # ------------------------------------------------------------------
    #  Topic Aggregation
    # ------------------------------------------------------------------

    def aggregate(self, hotsearch_list: List[HotSearchInfo]) -> List[TrendingTopicEnhanced]:
        self._hotsearch_list = hotsearch_list
        title_map = self._group_by_normalized(hotsearch_list)
        self.init_token_cache(hotsearch_list)
        return self._build_topics(title_map)

    def _group_by_normalized(self, hotsearch_list: List[HotSearchInfo]) -> Dict[str, list]:
        norm_map: Dict[str, list] = defaultdict(list)
        for hs in hotsearch_list:
            norm_map[self.normalize_title(hs.title)].append(hs)

        title_map: Dict[str, list] = defaultdict(list)
        merged = 0
        for _, entries in norm_map.items():
            counter = Counter(hs.title for hs in entries)
            best = counter.most_common(1)[0][0]
            title_map[best] = entries
            if len(counter) > 1:
                merged += 1
        if merged:
            print(f"    标准化去重：合并 {merged} 组仅标点差异的标题")
        return title_map

    def _build_topics(self, title_map: Dict[str, list]) -> List[TrendingTopicEnhanced]:
        topics: List[TrendingTopicEnhanced] = []
        computed_similar: set = set()

        for title, hs_list in title_map.items():
            platforms = list({hs.platform for hs in hs_list})
            platforms_name = list({hs.platform_name for hs in hs_list})
            ranks = [hs.rank for hs in hs_list]
            categories = {str(hs.category) if hs.category else "" for hs in hs_list}
            urls = list({hs.url for hs in hs_list if hs.url})
            is_new = any(hs.is_new for hs in hs_list)

            if title not in computed_similar:
                similar = [t for t in self._find_similar_titles(title) if t in title_map]
                computed_similar.add(title)
            else:
                similar = []

            for existing in topics:
                if title in existing.similar_titles and existing.title not in similar:
                    similar.append(existing.title)
                    if len(similar) >= 5:
                        break

            orig_cat = next((hs.category for hs in hs_list if hs.category), None)
            event_type = self._classify_single_topic(title, similar, orig_cat)

            topics.append(TrendingTopicEnhanced(
                title=title,
                platforms=platforms,
                platforms_name=platforms_name,
                platform_count=len(platforms),
                best_rank=min(ranks),
                avg_rank=sum(ranks) / len(ranks),
                heat_score=0.0,
                categories=categories,
                similar_titles=similar,
                keywords=[],
                event_type=event_type,
                is_new=is_new,
                urls=urls,
            ))
        return topics

    def _find_similar_titles(self, title: str, threshold: float = 0.7) -> List[str]:
        similar: List[str] = []
        title_words = self._title_words_cache.get(title)
        if title_words is None:
            return similar
        for hs in self._hotsearch_list:
            if hs.title == title:
                continue
            other = self._title_words_cache.get(hs.title)
            if not other:
                continue
            inter, union = len(title_words & other), len(title_words | other)
            if union > 0 and inter / union >= threshold:
                similar.append(hs.title)
        return similar[:5]

    # ------------------------------------------------------------------
    #  Single-topic Classification (lightweight, for event-level voting)
    # ------------------------------------------------------------------

    def _classify_single_topic(self, title: str, similar: List[str], orig_cat: str = None) -> str:
        scores: Dict[EventType, float] = defaultdict(float)
        all_titles = [title] + similar
        weights = self.config_manager.get_type_weight_coefficients()
        strong_excl = self.config_manager.get_politics_strong_exclusion()
        soft_excl = self.config_manager.get_politics_soft_exclusion()

        has_strong = any(any(w in t for w in strong_excl) for t in all_titles)
        has_soft = any(any(w in t for w in soft_excl) for t in all_titles)

        for t in all_titles:
            for et, kws in self.EVENT_KEYWORDS.items():
                s = sum(1 + len(kw) / 2.0 for kw in kws if kw in t)
                if et.value in weights:
                    s *= weights[et.value]
                if et == EventType.POLITICS:
                    if has_strong:
                        s = 0
                    elif has_soft:
                        s *= 0.5
                scores[et] += s

        norm = max(len(all_titles) - 1, 1)
        for et in scores:
            scores[et] /= norm

        if scores and max(scores.values()) > 0:
            best = max(scores, key=scores.get)
            if best == EventType.POLITICS and orig_cat and orig_cat not in ('politics', 'politic', '政治'):
                sorted_s = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                if len(sorted_s) >= 2 and sorted_s[1][1] > 0 and sorted_s[0][1] / sorted_s[1][1] < 1.5:
                    return "其他"
            return best.cn

        return self._fallback_classify(title, similar, orig_cat)

    def _fallback_classify(self, title: str, similar: List[str], orig_cat: str = None) -> str:
        text = " ".join([title] + similar)
        for et_str, kws in self.config_manager.get_fallback_priority_keywords().items():
            for kw in kws:
                if kw in text:
                    try:
                        result = EventType(et_str).cn
                    except ValueError:
                        result = et_str
                    if result == "政治" and orig_cat and orig_cat not in ('politics', 'politic', '政治'):
                        return "其他"
                    return result
        return "其他"

    # ------------------------------------------------------------------
    #  Keyword Extraction
    # ------------------------------------------------------------------

    def extract_keywords(self, hotsearch_list: List[HotSearchInfo]) -> List[KeywordInfoEnhanced]:
        if self.use_nlp:
            return self._extract_tfidf(hotsearch_list)
        return self._extract_basic(hotsearch_list)

    def _extract_tfidf(self, hotsearch_list: List[HotSearchInfo]) -> List[KeywordInfoEnhanced]:
        try:
            vectorizer = TfidfVectorizer(max_features=100, min_df=2, max_df=0.95, ngram_range=(1, 2))
            tfidf_matrix = vectorizer.fit_transform([hs.title for hs in hotsearch_list])
            features = vectorizer.get_feature_names_out()
            tfidf_scores = tfidf_matrix.sum(axis=0).A1
            kw_dict = dict(zip(features, tfidf_scores))

            counter: Dict[str, int] = defaultdict(int)
            platforms: Dict[str, set] = defaultdict(set)
            topics_map: Dict[str, list] = defaultdict(list)

            for hs in hotsearch_list:
                for w in self.tokenize(hs.title):
                    if w in self.STOP_WORDS:
                        continue
                    counter[w] += 1
                    platforms[w].add(hs.platform)
                    if len(topics_map[w]) < 3:
                        topics_map[w].append(hs.title)

            return [
                KeywordInfoEnhanced(
                    keyword=kw, weight=float(kw_dict.get(kw, cnt * 0.1)), count=cnt,
                    platforms=platforms[kw], related_topics=topics_map[kw],
                )
                for kw, cnt in counter.items() if cnt >= 2
            ]
        except Exception as e:
            print(f"TF-IDF 提取失败: {e}，使用基础方法")
            return self._extract_basic(hotsearch_list)

    def _extract_basic(self, hotsearch_list: List[HotSearchInfo]) -> List[KeywordInfoEnhanced]:
        counter: Dict[str, int] = defaultdict(int)
        platforms: Dict[str, set] = defaultdict(set)
        topics_map: Dict[str, list] = defaultdict(list)

        for hs in hotsearch_list:
            for w in re.findall(r'[\u4e00-\u9fa5]{2,}', hs.title):
                if w in self.STOP_WORDS:
                    continue
                counter[w] += 1
                platforms[w].add(hs.platform)
                if len(topics_map[w]) < 3:
                    topics_map[w].append(hs.title)

        return [
            KeywordInfoEnhanced(
                keyword=kw, weight=float(cnt), count=cnt,
                platforms=platforms[kw], related_topics=topics_map[kw],
            )
            for kw, cnt in counter.items() if cnt >= 2
        ]

    def add_keywords_to_topics(self, topics: List[TrendingTopicEnhanced]):
        for topic in topics:
            if self.use_nlp:
                kws = jieba.analyse.extract_tags(topic.title, topK=5, withWeight=False)
            else:
                kws = re.findall(r'[\u4e00-\u9fa5]{2,}', topic.title)
            topic.keywords = [kw for kw in kws if kw not in self.STOP_WORDS][:5]

    def calculate_heat_score(self, topics: List[TrendingTopicEnhanced]):
        if not topics:
            return

        # 基于各平台爬取数量计算权重（爬取越少的平台，出现在其上的话题越有价值）
        platform_items_count: Dict[str, int] = defaultdict(int)
        for hs in self._hotsearch_list:
            platform_items_count[hs.platform] += 1

        # 加权覆盖度归一化分母：全部平台权重之和（出现在所有平台时的理论最大值）
        total_weight = sum(1.0 / c for c in platform_items_count.values()) if platform_items_count else 1.0

        for t in topics:
            weighted_coverage = sum(
                1.0 / platform_items_count.get(p, 1) for p in t.platforms
            )
            normalized_coverage = weighted_coverage / total_weight

            t.heat_score = (
                normalized_coverage * 50
                + max(0, (1 - (t.best_rank / 10))) * 30
                + min(len(t.similar_titles) * 5, 20)
                + (5 if t.keywords and len(t.keywords) >= 2 else 0)
            )
