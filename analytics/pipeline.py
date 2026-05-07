# analytics/pipeline.py
"""
分析管道模块
提供 PipelineStep 抽象基类、AnalysisContext 共享上下文、AnalysisPipeline 可配置编排器，
以及所有具体的分析步骤实现。
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from core.models import (
    EventType,
    HotSearchInfo,
    TrendingTopicEnhanced,
    KeywordInfoEnhanced,
    EventInfoEnhanced,
    AnalysisOutputEnhanced,
    TrackedKeywordMatch,
    TrackedKeywordResult,
)
from core.config_manager import ConfigManager

from analytics.data_loader import DataLoader
from analytics.topic_aggregator import TopicAggregator
from analytics.event_clusterer import EventClusterer
from analytics.event_classifier import (
    EventClassifier,
    NLPClassificationStrategy,
    BasicClassificationStrategy,
    LLMClassificationStrategy,
)


# ======================================================================
#  Context
# ======================================================================

@dataclass
class AnalysisContext:
    """管道步骤间的共享上下文"""
    hotsearch_list: List[HotSearchInfo] = field(default_factory=list)
    trending_topics: List[TrendingTopicEnhanced] = field(default_factory=list)
    events: List[EventInfoEnhanced] = field(default_factory=list)
    keywords: List[KeywordInfoEnhanced] = field(default_factory=list)
    tracked_keywords: List[TrackedKeywordResult] = field(default_factory=list)
    category_distribution: Dict[str, int] = field(default_factory=dict)
    platform_distribution: Dict[str, int] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)
    data_time_range: str = ""
    use_nlp: bool = True
    use_llm: bool = False


# ======================================================================
#  PipelineStep
# ======================================================================

class PipelineStep(ABC):
    """分析管道步骤的抽象基类"""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def execute(self, ctx: AnalysisContext) -> None:
        ...


# ======================================================================
#  Concrete Steps
# ======================================================================

class LoadDataStep(PipelineStep):
    """Step: 加载热搜数据"""

    def __init__(self, loader: DataLoader):
        self._loader = loader

    def execute(self, ctx: AnalysisContext) -> None:
        if not ctx.hotsearch_list:
            ctx.hotsearch_list = self._loader.load()


class KeywordTrackingStep(PipelineStep):
    """Step: 关键词追踪（无视热度，子串匹配）"""

    def __init__(self, config_manager: ConfigManager):
        self._cfg = config_manager

    def execute(self, ctx: AnalysisContext) -> None:
        ctx.tracked_keywords = self._extract(ctx.hotsearch_list)

    def _extract(self, hs_list: List[HotSearchInfo]) -> List[TrackedKeywordResult]:
        try:
            tracking_cfg = self._cfg.user_config.get("keyword_tracking", {})
        except Exception:
            return []
        if not tracking_cfg.get("enabled", False):
            return []
        max_per = tracking_cfg.get("max_matches_per_keyword", 5)

        # 解析分组配置：groups 列表 + 兜底扁平 keywords
        groups_cfg = tracking_cfg.get("groups", [])
        flat_keywords = tracking_cfg.get("keywords", [])

        # 构建 [(label, group_name, [kw1_lower, kw2_lower, ...]), ...]
        # 支持两种格式：简写字符串 '关键词' / 完整字典 {name, keywords}
        keyword_groups: List[tuple] = []

        for group_cfg in groups_cfg:
            group_name = group_cfg.get("name", "")
            for kw_entry in group_cfg.get("keywords", []):
                if isinstance(kw_entry, dict):
                    label = kw_entry.get("name", "")
                    kw_list = kw_entry.get("keywords", [])
                else:
                    label = str(kw_entry)
                    kw_list = [label]
                if label and kw_list:
                    keyword_groups.append((label, group_name, [str(k).lower() for k in kw_list]))

        # 扁平列表中的关键词归入"未分组"
        for kw in flat_keywords:
            label = str(kw)
            keyword_groups.append((label, "", [label.lower()]))

        if not keyword_groups:
            return []

        title_items = [(hs.title.lower(), hs) for hs in hs_list]

        results: List[TrackedKeywordResult] = []
        for label, group_name, kw_lowers in keyword_groups:
            matched_titles = set()
            matches: List[TrackedKeywordMatch] = []
            for tl, hs in title_items:
                if any(kw_lower in tl for kw_lower in kw_lowers):
                    if hs.title not in matched_titles:
                        matched_titles.add(hs.title)
                        matches.append(TrackedKeywordMatch(
                            title=hs.title, platform_name=hs.platform_name,
                            rank=hs.rank, url=hs.url, is_new=hs.is_new,
                        ))
                        if len(matches) >= max_per:
                            break
            if matches:
                results.append(TrackedKeywordResult(
                    keyword=label, group=group_name,
                    keywords=[k for k in kw_lowers],
                    match_count=len(matches), matches=matches,
                ))

        # 按分组排序：有分组的在前，组内按匹配数降序；未分组的在最后
        results.sort(key=lambda r: (r.group == "", -r.match_count))

        if results:
            print(f"    追踪到 {len(results)} 个关键词，共 {sum(r.match_count for r in results)} 条匹配")
        return results


class AggregateTopicsStep(PipelineStep):
    """Step: 聚合相似热搜为话题"""

    def __init__(self, aggregator: TopicAggregator):
        self._agg = aggregator

    def execute(self, ctx: AnalysisContext) -> None:
        ctx.trending_topics = self._agg.aggregate(ctx.hotsearch_list)


class ExtractKeywordsStep(PipelineStep):
    """Step: 提取关键词并附加到话题"""

    def __init__(self, aggregator: TopicAggregator):
        self._agg = aggregator

    def execute(self, ctx: AnalysisContext) -> None:
        ctx.keywords = self._agg.extract_keywords(ctx.hotsearch_list)
        self._agg.add_keywords_to_topics(ctx.trending_topics)


class CalculateHeatScoreStep(PipelineStep):
    """Step: 计算热度分数"""

    def __init__(self, aggregator: TopicAggregator):
        self._agg = aggregator

    def execute(self, ctx: AnalysisContext) -> None:
        self._agg.calculate_heat_score(ctx.trending_topics)


class FilterLowHeatStep(PipelineStep):
    """Step: 过滤低热度话题，减少噪音和无效 LLM 调用"""

    def __init__(self, min_heat_score: float = 15):
        self._min = min_heat_score

    def execute(self, ctx: AnalysisContext) -> None:
        if self._min <= 0:
            return
        before = len(ctx.trending_topics)
        ctx.trending_topics = [
            t for t in ctx.trending_topics if t.heat_score >= self._min
        ]
        removed = before - len(ctx.trending_topics)
        if removed > 0:
            print(f"    热度过滤: {before} → {len(ctx.trending_topics)} "
                  f"(移除 {removed} 条低于 {self._min} 分的话题)")


class ClusterEventsStep(PipelineStep):
    """Step: 聚类事件"""

    def __init__(self, clusterer: EventClusterer):
        self._clusterer = clusterer

    def execute(self, ctx: AnalysisContext) -> None:
        ctx.events = self._clusterer.cluster(ctx.trending_topics)


class ClassifyEventsStep(PipelineStep):
    """Step: 事件类型分类（支持 LLM 部分分类 + 自动降级）"""

    def __init__(self, primary: EventClassifier,
                 fallback: Optional[EventClassifier] = None,
                 event_keywords: Optional[Dict[EventType, List[str]]] = None,
                 tokenizer: Optional[Callable[[str], set]] = None,
                 llm_max: int = 0):
        self._primary = primary
        self._fallback = fallback
        self._keywords = event_keywords or {}
        self._tokenizer = tokenizer
        self._llm_max = llm_max

    def execute(self, ctx: AnalysisContext) -> None:
        events = ctx.events
        if not events:
            return

        if self._llm_max > 0 and len(events) > self._llm_max:
            sorted_ev = sorted(events, key=lambda x: x.heat_score, reverse=True)
            llm_ev = sorted_ev[:self._llm_max]
            fast_ev = sorted_ev[self._llm_max:]
            print(f"    LLM 分类 Top {self._llm_max}/{len(events)} 个事件，"
                  f"其余 {len(fast_ev)} 个快速分类")
            self._primary.classify(llm_ev, self._keywords, self._tokenizer)
            if self._fallback:
                self._fallback.classify(fast_ev, self._keywords, self._tokenizer)
        else:
            self._primary.classify(events, self._keywords, self._tokenizer)

        EventClassifier.propagate_to_topics(events)


class CollectStatisticsStep(PipelineStep):
    """Step: 收集统计分布数据"""

    def execute(self, ctx: AnalysisContext) -> None:
        ctx.category_distribution = _category_dist(ctx.trending_topics)
        ctx.platform_distribution = _platform_dist(ctx.hotsearch_list)
        ctx.statistics = _calc_stats(ctx.trending_topics, ctx.hotsearch_list)
        ctx.data_time_range = _time_range(ctx.hotsearch_list)


# ======================================================================
#  Pipeline
# ======================================================================

class AnalysisPipeline:
    """可配置的分析管道，步骤可插拔、可排序"""

    def __init__(self, steps: Optional[List[PipelineStep]] = None):
        self._steps: List[PipelineStep] = steps or []

    # -- Mutation API (fluent) --

    def add_step(self, step: PipelineStep) -> 'AnalysisPipeline':
        self._steps.append(step)
        return self

    def insert_before(self, step_class: type, new_step: PipelineStep) -> 'AnalysisPipeline':
        for i, s in enumerate(self._steps):
            if isinstance(s, step_class):
                self._steps.insert(i, new_step)
                return self
        self._steps.append(new_step)
        return self

    def insert_after(self, step_class: type, new_step: PipelineStep) -> 'AnalysisPipeline':
        for i, s in enumerate(self._steps):
            if isinstance(s, step_class):
                self._steps.insert(i + 1, new_step)
                return self
        self._steps.append(new_step)
        return self

    def remove_step(self, step_class: type) -> 'AnalysisPipeline':
        self._steps = [s for s in self._steps if not isinstance(s, step_class)]
        return self

    def replace_step(self, step_class: type, new_step: PipelineStep) -> 'AnalysisPipeline':
        self._steps = [new_step if isinstance(s, step_class) else s for s in self._steps]
        return self

    # -- Execution --

    def run(self, ctx: AnalysisContext) -> AnalysisOutputEnhanced:
        """依次执行所有步骤，返回分析结果"""
        import traceback
        print("开始分析热搜内容...")
        total = len(self._steps)
        for i, step in enumerate(self._steps, 1):
            print(f"  [{i}/{total}] {step.name}")
            try:
                step.execute(ctx)
            except Exception as e:
                print(f"  ✗ {step.name} 执行失败: {e}")
                traceback.print_exc()
                raise

        method = "llm" if ctx.use_llm else ("nlp" if ctx.use_nlp else "basic")
        ctx.analysis_method = method

        output = AnalysisOutputEnhanced(
            output_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data_time_range=ctx.data_time_range,
            total_topics=len(ctx.trending_topics),
            analysis_method=method,
            top_topics=sorted(ctx.trending_topics, key=lambda x: x.heat_score, reverse=True)[:20],
            trending_events=sorted(ctx.events, key=lambda x: x.heat_score, reverse=True)[:10],
            keywords=sorted(ctx.keywords, key=lambda x: x.weight, reverse=True)[:30],
            category_distribution=ctx.category_distribution,
            platform_distribution=ctx.platform_distribution,
            statistics=ctx.statistics,
            tracked_keywords=ctx.tracked_keywords,
        )
        print("分析完成！")
        return output


# ======================================================================
#  Module-level statistic helpers
# ======================================================================

def _category_dist(topics: List[TrendingTopicEnhanced]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for t in topics:
        counts[t.event_type or "其他"] += 1
    return dict(counts)


def _platform_dist(hs_list: List[HotSearchInfo]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for hs in hs_list:
        counts[hs.platform_name] += 1
    return dict(counts)


def _calc_stats(topics: List[TrendingTopicEnhanced], hs_list: List[HotSearchInfo]) -> Dict[str, Any]:
    ranks = [hs.rank for hs in hs_list if hs.rank > 0]
    pc: Dict[str, int] = defaultdict(int)
    for hs in hs_list:
        pc[hs.platform] += 1
    return {
        'total_hotsearch_count': len(hs_list),
        'platform_count': len(pc),
        'avg_rank': sum(ranks) / len(ranks) if ranks else 0,
        'top_rank_count': len([r for r in ranks if r == 1]),
        'max_platforms_per_topic': max((t.platform_count for t in topics), default=0),
        'avg_hotsearch_per_platform': len(hs_list) / len(pc) if pc else 0,
    }


def _time_range(hs_list: List[HotSearchInfo]) -> str:
    times = [hs.fetch_time for hs in hs_list if hs.fetch_time]
    return f"{min(times)} 至 {max(times)}" if times else "未知"
