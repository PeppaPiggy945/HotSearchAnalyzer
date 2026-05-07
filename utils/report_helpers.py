# utils/report_helpers.py
"""
报告生成公共逻辑 — 三个报告生成器（HTML / Email / Markdown）共享的数据处理函数。

提取自 html_report_generator.py、email_report_generator.py、md_report_generator.py 中
高度相似的 _build_top_topics 和 _build_trending_events 数据准备逻辑。
"""

from collections import defaultdict
from typing import List, Optional, Tuple

from core.models import (
    AnalysisOutput,
    EventInfoEnhanced,
    TrendingTopicEnhanced,
    get_event_type_style,
    heat_rank_color,
)


def prepare_trending_events(
    analysis_output: AnalysisOutput,
    top_n: int = 10,
) -> Tuple[List[EventInfoEnhanced], float]:
    """
    准备热门事件数据：过滤低热度 → 排序 → 取 Top N。

    Args:
        analysis_output: 分析输出
        top_n: 返回最大事件数

    Returns:
        (events_list, max_heat) — 排序后的 Top N 事件列表和其中最大热度
    """
    events = analysis_output.trending_events
    if not events:
        return [], 1

    all_scores = [e.heat_score for e in events]
    avg_heat = sum(all_scores) / len(all_scores) if all_scores else 0
    threshold = avg_heat * 0.5

    filtered = [e for e in events if e.heat_score >= threshold]
    sorted_events = sorted(filtered, key=lambda x: x.heat_score, reverse=True)[:top_n]
    max_heat = max((e.heat_score for e in sorted_events), default=1)

    return sorted_events, max_heat


def prepare_top_topics(
    analysis_output: AnalysisOutput,
) -> Tuple[List[TrendingTopicEnhanced], dict]:
    """
    准备热门话题数据：去重 → 按分类分组 → 排序 → 计算每类颜色。

    Args:
        analysis_output: 分析输出

    Returns:
        (filtered_topics, cat_colors) — 去重后的话题列表和分类→颜色映射
    """
    # 去重
    seen_titles = set()
    filtered = []
    for topic in analysis_output.top_topics:
        if topic.title in seen_titles:
            continue
        seen_titles.add(topic.title)
        seen_titles.update(topic.similar_titles)
        filtered.append(topic)

    # 按分类分组
    topics_by_type = defaultdict(list)
    for topic in filtered:
        topics_by_type[topic.event_type].append(topic)

    # 计算每个分类的平均热度 → 分配颜色
    cat_avg_heat = {}
    for cat, topics in topics_by_type.items():
        cat_avg_heat[cat] = sum(t.heat_score for t in topics) / len(topics)

    all_avg = list(cat_avg_heat.values())
    cat_colors = {
        cat: heat_rank_color(
            sorted(set(all_avg), reverse=True).index(avg) + 1,
            len(set(all_avg))
        )
        for cat, avg in cat_avg_heat.items()
    }

    # 按话题数量降序排列，"其他"始终放最后
    sorted_types = sorted(
        topics_by_type.items(),
        key=lambda x: (x[0] == "其他", -len(x[1]))
    )

    # 根据总数据量动态调整每类展示上限
    total = len(filtered)
    top_n = 15 if total > 100 else (10 if total > 50 else 8)

    # 按热度排序每个分类内的话题
    result_topics = []
    for category, topics in sorted_types:
        sorted_topics = sorted(topics, key=lambda x: x.heat_score, reverse=True)[:top_n]
        result_topics.extend(sorted_topics)

    return filtered, cat_colors


def get_top_n_per_category() -> int:
    """根据话题总量动态计算每类展示上限"""
    # 注意：此函数需要话题总量，但为简化调用保留
    # 调用方更推荐使用 prepare_top_topics 的返回值直接使用
    return 15


def get_sorted_categories(
    topics_by_type: dict,
) -> list:
    """
    按话题数量降序排列各类别，"其他"始终放最后。

    Args:
        topics_by_type: {category: [topics]} 字典

    Returns:
        排序后的 (category, topics) 列表
    """
    return sorted(
        topics_by_type.items(),
        key=lambda x: (x[0] == "其他", -len(x[1]))
    )


def get_cat_colors(topics_by_type: dict) -> dict:
    """
    计算每个分类的平均热度并分配颜色。

    Args:
        topics_by_type: {category: [topics]} 字典

    Returns:
        {category: hex_color} 映射
    """
    cat_avg_heat = {}
    for cat, topics in topics_by_type.items():
        cat_avg_heat[cat] = sum(t.heat_score for t in topics) / len(topics)

    all_avg = list(cat_avg_heat.values())
    return {
        cat: heat_rank_color(
            sorted(set(all_avg), reverse=True).index(avg) + 1,
            len(set(all_avg))
        )
        for cat, avg in cat_avg_heat.items()
    }


def format_platforms(platforms_name: list, max_show: int = 5) -> str:
    """
    格式化平台列表为展示字符串。

    Args:
        platforms_name: 平台中文名列表
        max_show: 最多展示几个平台名

    Returns:
        如 "微博、百度、抖音 等7个平台"
    """
    if not platforms_name:
        return ""
    names = platforms_name[:max_show]
    result = "、".join(names)
    if len(platforms_name) > max_show:
        result += f" 等{len(platforms_name)}个平台"
    return result
