# analytics/smart_content_analyzer.py
"""
智能热搜内容分析模块 — 门面（Facade）

对外保持与旧版完全一致的公共接口：
  - SmartContentAnalyzer 类
  - analyze_content_smart() 便捷函数

内部已重构为 Pipeline + Strategy 架构，具体实现分布在：
  - analytics/data_loader.py          数据加载
  - analytics/topic_aggregator.py     话题聚合 / 关键词提取 / 热度计算
  - analytics/event_clusterer.py      事件聚类（策略可插拔）
  - analytics/event_classifier.py     事件分类（策略可插拔）
  - analytics/pipeline.py             管道编排
"""

from pathlib import Path
from typing import Dict, List, Optional

from config.settings import get_settings
from core.config_manager import ConfigManager
from core.models import (
    EventType, HotSearchInfo, TrendingTopicEnhanced,
    KeywordInfoEnhanced, EventInfoEnhanced, AnalysisOutputEnhanced,
    TrackedKeywordResult, TrackedKeywordMatch,
)

from analytics.pipeline import (
    AnalysisPipeline,
    AnalysisContext,
    PipelineStep,
    LoadDataStep,
    KeywordTrackingStep,
    AggregateTopicsStep,
    ExtractKeywordsStep,
    CalculateHeatScoreStep,
    FilterLowHeatStep,
    ClusterEventsStep,
    ClassifyEventsStep,
    CollectStatisticsStep,
)
from analytics.llm_middleware import (
    ValidateClustersStep,
    PickRepresentativeTitleStep,
)
from analytics.data_loader import DataLoader
from analytics.topic_aggregator import TopicAggregator
from analytics.event_clusterer import (
    EventClusterer,
    KMeansClusteringStrategy,
    GreedyClusteringStrategy,
)
from analytics.event_classifier import (
    EventClassifier,
    NLPClassificationStrategy,
    BasicClassificationStrategy,
    LLMClassificationStrategy,
)

try:
    import jieba
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False

from analytics.llm_classifier import LLM_AVAILABLE as LLM_LIB_AVAILABLE

# ---- Backward-compatible aliases ----
TrendingTopic = TrendingTopicEnhanced
KeywordInfo = KeywordInfoEnhanced
EventInfo = EventInfoEnhanced
AnalysisOutput = AnalysisOutputEnhanced


class SmartContentAnalyzer:
    """智能热搜内容分析器（门面）"""

    def __init__(self, data_dir: str = None, use_nlp: bool = True, use_llm: bool = False):
        self.settings = get_settings()
        self.data_dir: Path = Path(data_dir) if data_dir else self.settings.paths.DATA_DIR / "HotSearchResult"

        # NLP / LLM 可用性
        self.use_nlp = use_nlp and NLP_AVAILABLE
        if use_llm:
            self.use_llm = LLM_LIB_AVAILABLE
        else:
            try:
                cfg = ConfigManager().user_config.get("llm", {})
                self.use_llm = cfg.get("enabled", False) and LLM_LIB_AVAILABLE
            except Exception:
                self.use_llm = False

        self.config_manager = ConfigManager()

        # 初始化日志
        if self.use_llm:
            print("使用 LLM 智能分类模式（Qwen2.5）")
        else:
            print("使用 NLP 智能分析模式")
            jieba.setLogLevel(jieba.logging.INFO)

        # ---- 核心组件 ----
        self._loader = DataLoader(self.data_dir, self.use_nlp)
        self._aggregator = TopicAggregator(self.config_manager, self.use_nlp)

        # ---- 构建管道 ----
        self._pipeline = self._build_pipeline()

    # ------------------------------------------------------------------
    #  Pipeline Construction
    # ------------------------------------------------------------------

    def _build_pipeline(self) -> AnalysisPipeline:
        agg = self._aggregator
        cfg = self.config_manager
        keywords = agg.EVENT_KEYWORDS
        tokenizer = agg.tokenize
        same_fn = agg.is_same_event

        # 聚类策略
        if self.use_nlp:
            clusterer = EventClusterer(KMeansClusteringStrategy(same_fn))
        else:
            clusterer = EventClusterer(GreedyClusteringStrategy(same_fn))

        # 分类策略
        if self.use_llm:
            llm_max = cfg.analytics_config.get("llm", {}).get("max_events", 0)
            primary = EventClassifier(
                LLMClassificationStrategy(cfg),
                NLPClassificationStrategy(cfg),
            )
            fallback = EventClassifier(
                NLPClassificationStrategy(cfg),
                BasicClassificationStrategy(cfg),
            )
            classify_step = ClassifyEventsStep(
                primary, fallback, keywords, tokenizer, llm_max,
            )
        elif self.use_nlp:
            primary = EventClassifier(
                NLPClassificationStrategy(cfg),
                BasicClassificationStrategy(cfg),
            )
            classify_step = ClassifyEventsStep(primary, event_keywords=keywords, tokenizer=tokenizer)
        else:
            primary = EventClassifier(BasicClassificationStrategy(cfg))
            classify_step = ClassifyEventsStep(primary, event_keywords=keywords, tokenizer=tokenizer)

        # 话题热度过滤（在聚类/分类之前截断噪音）
        min_heat = cfg.analytics_config.get("filter", {}).get("min_heat_score", 15)

        return AnalysisPipeline([
            LoadDataStep(self._loader),
            KeywordTrackingStep(cfg),
            AggregateTopicsStep(agg),
            ExtractKeywordsStep(agg),
            CalculateHeatScoreStep(agg),
            FilterLowHeatStep(min_heat),
            ClusterEventsStep(clusterer),
            ValidateClustersStep(),        # LLM: 聚类校验（拆分不相关话题）
            PickRepresentativeTitleStep(),  # LLM: 代表标题选取
            classify_step,
            CollectStatisticsStep(),
        ])

    # ------------------------------------------------------------------
    #  Public API (backward compatible)
    # ------------------------------------------------------------------

    def load_data(self) -> int:
        """加载所有热搜数据"""
        hs_list = self._loader.load()
        return len(hs_list)

    def analyze(self) -> AnalysisOutputEnhanced:
        """执行内容分析"""
        ctx = AnalysisContext(
            hotsearch_list=[],
            use_nlp=self.use_nlp,
            use_llm=self.use_llm,
        )
        return self._pipeline.run(ctx)

    def print_output(self, output: AnalysisOutputEnhanced):
        """打印开发者向控制台输出（含诊断信息）"""
        w = 80
        print()
        print("=" * w)
        print(f"[ANALYSIS] SmartContentAnalyzer Output")
        print(f"  method       : {output.analysis_method}")
        print(f"  output_time  : {output.output_time}")
        print(f"  data_range   : {output.data_time_range}")
        print(f"  total_topics : {output.total_topics}")
        print("=" * w)

        # --- 统计概览 ---
        print(f"\n[STATISTICS]")
        stats = output.statistics or {}
        labels = {
            'total_hotsearch_count': 'total_hotsearch',
            'platform_count': 'platforms',
            'avg_rank': 'avg_rank',
            'top_rank_count': 'top_rank_count',
            'max_platforms_per_topic': 'max_platforms_per_topic',
            'avg_hotsearch_per_platform': 'avg_per_platform',
            'analysis_method': 'analysis_method',
        }
        for k, v in stats.items():
            label = labels.get(k, k)
            if isinstance(v, float):
                print(f"  {label:<30s} {v:>10.2f}")
            else:
                print(f"  {label:<30s} {v!s:>10}")

        # --- 关键词追踪 ---
        tracked = output.tracked_keywords if hasattr(output, 'tracked_keywords') else []
        if tracked:
            print(f"\n[KEYWORD TRACKING] ({len(tracked)} keywords)")
            current_group = None
            for tk in tracked:
                if tk.group != current_group:
                    current_group = tk.group
                    group_label = f"Group: \"{tk.group}\"" if tk.group else "Group: (ungrouped)"
                    print(f"\n  --- {group_label} ---")
                print(f"  \"{tk.keyword}\"  ({tk.match_count} matches)")
                for j, m in enumerate(tk.matches, 1):
                    new_tag = " [NEW]" if m.is_new else ""
                    print(f"    {j}. [{m.platform_name:<6s}] rank={m.rank:<3d} {m.title}{new_tag}")

        # --- 类型分布 ---
        if output.category_distribution:
            print(f"\n[CATEGORY DISTRIBUTION]")
            total_cat = sum(output.category_distribution.values())
            for cat, cnt in sorted(output.category_distribution.items(), key=lambda x: x[1], reverse=True):
                pct = cnt / total_cat * 100 if total_cat > 0 else 0
                bar_len = int(pct / 100 * 30)
                bar = "#" * bar_len + "-" * (30 - bar_len)
                print(f"  {str(cat):<14s} {cnt:>4d} ({pct:>5.1f}%)  {bar}")

        # --- 平台分布 ---
        if output.platform_distribution:
            print(f"\n[PLATFORM DISTRIBUTION]")
            total_plat = sum(output.platform_distribution.values())
            for plat, cnt in sorted(output.platform_distribution.items(), key=lambda x: x[1], reverse=True):
                pct = cnt / total_plat * 100 if total_plat > 0 else 0
                print(f"  {plat:<20s} {cnt:>4d} ({pct:>5.1f}%)")

        # --- 热门话题 TOP 20 ---
        print(f"\n[TOP TOPICS] (top {len(output.top_topics)})")
        for i, topic in enumerate(output.top_topics, 1):
            new_tag = " [NEW]" if topic.is_new else ""
            print(f"  {i:>2}. [{str(topic.event_type):<6s}] {topic.title}{new_tag}")
            print(f"      heat={topic.heat_score:>7.1f}  rank={topic.best_rank:>2d}  platforms={topic.platform_count}  "
                  f"[{', '.join(topic.platforms_name)}]")
            if topic.keywords:
                print(f"      keywords: {', '.join(topic.keywords)}")
            if topic.similar_titles:
                print(f"      similar({len(topic.similar_titles)}): {', '.join(topic.similar_titles[:3])}")

        # --- 热门事件 TOP 10 ---
        print(f"\n[TRENDING EVENTS] (top {len(output.trending_events)})")
        for i, event in enumerate(output.trending_events, 1):
            print(f"  {i:>2}. {event.title}")
            print(f"      type={str(event.event_type):<6s}  conf={event.confidence:.2f}  "
                  f"heat={event.heat_score:>7.1f}  topics={event.topic_count}  cluster_id={event.cluster_id}")
            print(f"      platforms: {', '.join(event.platforms_name)}")
            if event.description:
                desc = event.description[:100] + ("..." if len(event.description) > 100 else "")
                print(f"      desc: {desc}")

        # --- 关键词 ---
        if output.keywords:
            print(f"\n[TOP KEYWORDS] (top {len(output.keywords)})")
            for i in range(0, len(output.keywords), 6):
                chunk = output.keywords[i:i + 6]
                parts = [f"{kw.keyword}({kw.weight:.2f},n={kw.count})" for kw in chunk]
                print(f"  {' | '.join(parts)}")

        print(f"\n{'=' * w}")

    def save_output(self, output: AnalysisOutputEnhanced, output_file: str = None):
        saved_path = output.save(output_file)
        print(f"输出结果已保存到: {saved_path}")

    # ------------------------------------------------------------------
    #  Pipeline Access (for advanced users)
    # ------------------------------------------------------------------

    @property
    def pipeline(self) -> AnalysisPipeline:
        """访问底层管道，支持动态添加/移除/替换步骤"""
        return self._pipeline

    @property
    def aggregator(self) -> TopicAggregator:
        return self._aggregator


# ======================================================================
#  Convenience Function
# ======================================================================

def analyze_content_smart(
    data_dir: str = None,
    output_file: str = None,
    verbose: bool = True,
    use_nlp: bool = True,
    use_llm: bool = False,
) -> AnalysisOutputEnhanced:
    """智能分析热搜内容的便捷函数"""
    analyzer = SmartContentAnalyzer(data_dir, use_nlp=use_nlp, use_llm=use_llm)
    output = analyzer.analyze()
    if verbose:
        analyzer.print_output(output)
    if output_file:
        analyzer.save_output(output, output_file)
    return output


if __name__ == "__main__":
    output = analyze_content_smart(use_nlp=True)
