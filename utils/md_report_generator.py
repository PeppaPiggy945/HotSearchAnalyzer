"""
报告生成模块
根据模板文件和分析结果生成Markdown格式分析报告
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from config.settings import get_settings
from core.logger import get_logger
from core.models import (
    AnalysisOutput,
    AnalysisOutputEnhanced,
    get_event_type_style,
)
from utils.report_helpers import (
    prepare_trending_events,
    get_sorted_categories,
    get_cat_colors,
    format_platforms,
)


class ReportGenerator:
    """报告生成器"""

    def __init__(self):
        """初始化报告生成器"""
        self.logger = get_logger(__name__)
        self.settings = get_settings()
        self.base_dir = self.settings.paths.BASE_DIR

        # 报告模板路径
        self.template_dir = self.settings.paths.TEMPLATES_DIR
        self.report_template_path = self.template_dir / "分析报告_Report.md"

        # 报告输出目录
        self.report_output_dir = self.base_dir / "outputs"
        self.report_output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _proportion_bar(ratio: float, length: int = 12) -> str:
        """将 0~1 的比例转换为可视化进度条（用于分布占比）"""
        ratio = max(0.0, min(ratio, 1.0))
        filled = max(int(ratio * length), 1)
        return '█' * filled + '░' * (length - filled)

    @staticmethod
    def _heat_level(score: float, max_score: float = 100.0) -> str:
        """将热度分数转换为等级标签（🔥×等级）"""
        ratio = score / max_score if max_score > 0 else 0
        if ratio >= 0.8:
            return '🔥🔥🔥'
        elif ratio >= 0.5:
            return '🔥🔥'
        elif ratio >= 0.25:
            return '🔥'
        else:
            return ''

    def _load_template(self, template_path: Path) -> str:
        """
        加载报告模板

        Args:
            template_path: 模板文件路径

        Returns:
            模板内容字符串
        """
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise FileNotFoundError(f"无法加载模板文件 {template_path}: {e}")

    def _generate_filename(self, analysis_output: AnalysisOutput) -> str:
        """
        生成报告文件名

        Args:
            analysis_output: 分析输出对象

        Returns:
            文件名
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"hotsearch_report_{timestamp}.md"

    def _build_statistics_table(self, statistics: Dict[str, Any]) -> str:
        """
        构建统计信息表格

        Args:
            statistics: 统计信息字典

        Returns:
            Markdown表格字符串
        """
        if not statistics:
            return "无统计数据"

        lines = ["| 指标 | 数值 |", "|------|------|"]
        for key, value in statistics.items():
            if isinstance(value, float):
                lines.append(f"| {key} | {value:.2f} |")
            else:
                lines.append(f"| {key} | {value} |")

        return '\n'.join(lines)

    def _build_top_topics_content(self, analysis_output: AnalysisOutput) -> str:
        """
        构建热门话题内容（按事件类型分类，紧凑排版）

        Args:
            analysis_output: 分析输出对象

        Returns:
            Markdown内容字符串
        """
        from collections import defaultdict

        # 过滤相似话题：保留热度最高的代表话题
        seen_titles = set()
        filtered_topics = []
        for topic in analysis_output.top_topics:
            if topic.title in seen_titles:
                continue
            seen_titles.add(topic.title)
            seen_titles.update(topic.similar_titles)
            filtered_topics.append(topic)

        # 按事件类型分组
        topics_by_type = defaultdict(list)
        for topic in filtered_topics:
            topics_by_type[topic.event_type].append(topic)

        # 根据总数据量动态调整每类展示上限
        total = len(filtered_topics)
        top_n = 15 if total > 100 else (10 if total > 50 else 8)

        lines = []

        sorted_types = get_sorted_categories(topics_by_type)

        for category, topics in sorted_types:
            if not topics:
                continue
            sorted_topics = sorted(topics, key=lambda x: x.heat_score, reverse=True)[:top_n]
            _, _, icon = get_event_type_style(category)
            cn_name = category  # category 已经是中文字符串
            lines.append(f"### {icon} {cn_name}")
            lines.append("")

            for i, topic in enumerate(sorted_topics, 1):
                new_tag = "`NEW` " if topic.is_new else ""
                lines.append(f"**{i}.** {new_tag}{topic.title}")
                lines.append("")

        if not lines:
            lines.append("暂无热门话题数据")

        return '\n'.join(lines)

    def _build_trending_events_content(self, analysis_output: AnalysisOutput) -> str:
        """
        构建热门事件内容（用户友好排版）

        Args:
            analysis_output: 分析输出对象

        Returns:
            Markdown内容字符串
        """
        events, max_event_heat = prepare_trending_events(analysis_output, top_n=10)

        if not events:
            return "暂无热门事件数据"

        lines = []
        for i, event in enumerate(events, 1):
            cn_type, _, icon = get_event_type_style(event.event_type or "其他")
            level = self._heat_level(event.heat_score, max_score=max_event_heat)

            platform_str = format_platforms(
                event.platforms_name if isinstance(event.platforms_name, list) else []
            )

            lines.append(f"### {i}. {event.title}")
            meta = f"> {icon} **{cn_type}** ｜ {platform_str} ｜ {event.topic_count} 个相关话题"
            if level:
                meta += f" ｜ {level}"
            lines.append(meta)
            lines.append("")

        if not lines:
            lines.append("暂无符合热度阈值的热门事件")

        return '\n'.join(lines)

    def _build_keywords_content(self, analysis_output: AnalysisOutput) -> str:
        """
        构建热门关键词内容

        Args:
            analysis_output: 分析输出对象

        Returns:
            Markdown内容字符串
        """
        keywords_per_line = 6
        lines = []
        
        for i in range(0, len(analysis_output.keywords), keywords_per_line):
            line_keywords = analysis_output.keywords[i:i+keywords_per_line]
            
            # 如果是增强版，显示权重
            if all(hasattr(kw, 'weight') for kw in line_keywords):
                line_str = " | ".join([
                    f"{kw.keyword}({kw.count}, 权重:{kw.weight:.3f})"
                    if hasattr(kw, 'weight') and kw.weight > 0
                    else f"{kw.keyword}({kw.count})"
                    for kw in line_keywords
                ])
            else:
                line_str = " | ".join([f"{kw.keyword}({kw.count})" for kw in line_keywords])
            
            lines.append(f"- {line_str}")
        
        return '\n'.join(lines)

    def _build_tracked_keywords_content(self, analysis_output: AnalysisOutput) -> str:
        """
        构建关键词追踪内容（置顶区域）

        Args:
            analysis_output: 分析输出对象

        Returns:
            Markdown内容字符串，无追踪时返回空字符串
        """
        tracked = getattr(analysis_output, 'tracked_keywords', None)
        if not tracked:
            return ""

        # 按分组聚合
        from collections import OrderedDict
        grouped: OrderedDict[str, list] = OrderedDict()
        for tk in tracked:
            grouped.setdefault(tk.group, []).append(tk)

        lines = ["## 🔍 关键词追踪", ""]
        for group_name, tk_list in grouped.items():
            display_name = group_name if group_name else "其他关键词"
            total = sum(t.match_count for t in tk_list)
            lines.append(f"### {display_name}（{total} 条匹配）")
            lines.append("")
            for tk in tk_list:
                lines.append(f"#### 「{tk.keyword}」（{tk.match_count} 条匹配）")
                lines.append("")
                for j, m in enumerate(tk.matches, 1):
                    new_tag = " `NEW`" if m.is_new else ""
                    rank_str = f"排名 #{m.rank}  |  " if m.rank > 0 else ""
                    lines.append(f"{j}. {m.title}{new_tag}")
                    lines.append(f"   > {rank_str}{m.platform_name}")
                lines.append("")

        return '\n'.join(lines)

    def _build_category_distribution_content(self, analysis_output: AnalysisOutput) -> str:
        """
        构建分类分布内容（带可视化条形图）

        Args:
            analysis_output: 分析输出对象

        Returns:
            Markdown表格字符串
        """
        dist = analysis_output.category_distribution
        if not dist:
            return "暂无分类数据"

        total_count = sum(dist.values())

        lines = ["| 分类 | 数量 | 占比 | 分布 |", "|:-----|-----:|-----:|:------|"]

        # 按数量降序展示所有实际出现的分类
        sorted_dist = sorted(dist.items(), key=lambda x: x[1], reverse=True)
        for category, count in sorted_dist:
            pct = count / total_count * 100 if total_count > 0 else 0
            bar = self._proportion_bar(pct / 100, length=12)
            _, _, icon = get_event_type_style(category)
            cn_name = category if category else "其他"
            lines.append(f"| {icon} {cn_name} | {count} | {pct:.1f}% | {bar} |")

        return '\n'.join(lines)

    def _build_platform_distribution_content(self, analysis_output: AnalysisOutput) -> str:
        """
        构建平台分布内容（带可视化条形图）

        Args:
            analysis_output: 分析输出对象

        Returns:
            Markdown表格字符串
        """
        dist = analysis_output.platform_distribution
        if not dist:
            return "暂无平台数据"

        total = sum(dist.values())

        lines = ["| 平台 | 热搜数 | 占比 | 分布 |", "|:-----|------:|-----:|:------|"]

        for platform, count in sorted(dist.items(), key=lambda x: x[1], reverse=True):
            pct = count / total * 100 if total > 0 else 0
            bar = self._proportion_bar(pct / 100, length=12)
            lines.append(f"| {platform} | {count} | {pct:.1f}% | {bar} |")

        return '\n'.join(lines)

    def generate_report(
        self,
        analysis_output: AnalysisOutput,
    ) -> str:
        """
        生成分析报告

        Args:
            analysis_output: 分析输出对象

        Returns:
            生成的报告内容
        """
        self.logger.info("开始生成Markdown报告")
        template = self._load_template(self.report_template_path)

        # 美化数据时间范围：去掉下划线
        data_range = analysis_output.data_time_range.replace('_', ' ')

        replacements = {
            '{{output_time}}': analysis_output.output_time,
            '{{data_time_range}}': data_range,
            '{{total_topics}}': str(analysis_output.total_topics),
            '{{tracked_keywords_content}}': self._build_tracked_keywords_content(analysis_output),
            '{{trending_events_content}}': self._build_trending_events_content(analysis_output),
            '{{top_topics_content}}': self._build_top_topics_content(analysis_output),
            '{{category_distribution_content}}': self._build_category_distribution_content(analysis_output),
            '{{platform_distribution_content}}': self._build_platform_distribution_content(analysis_output),
        }

        report = template
        for placeholder, content in replacements.items():
            report = report.replace(placeholder, content)

        return report

    def get_report_summary(self) -> Dict[str, Any]:
        """
        获取已生成的报告摘要

        Returns:
            报告摘要信息
        """
        summary = {
            "report_dir": str(self.report_output_dir),
            "template": str(self.report_template_path),
            "generated_reports": []
        }

        # 统计已生成的报告文件
        if self.report_output_dir.exists():
            for file_path in sorted(self.report_output_dir.glob("hotsearch_report_*.md"), reverse=True):
                file_info = {
                    "filename": file_path.name,
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "created": datetime.fromtimestamp(file_path.stat().st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                }
                summary["generated_reports"].append(file_info)

        return summary


# ==================== 便捷函数 ====================

def generate_analysis_report(
    analysis_output: AnalysisOutput,
) -> str:
    """
    便捷函数：生成分析报告

    Args:
        analysis_output: 分析输出对象

    Returns:
        生成的报告内容
    """
    generator = ReportGenerator()
    return generator.generate_report(analysis_output)


if __name__ == "__main__":
    # 测试代码
    import sys
    from core.models import TrendingTopic, EventInfo, KeywordInfo, EventType

    print("=" * 60)
    print("报告生成器测试")
    print("=" * 60)

    generator = ReportGenerator()

    # 打印报告配置摘要
    print("\n" + "=" * 60)
    print("报告配置摘要:")
    summary = generator.get_report_summary()
    print(summary)

    # 创建测试数据
    test_output = AnalysisOutput(
        output_time="2026-04-10 14:30:00",
        data_time_range="2026-04-09 至 2026-04-10",
        total_topics=100,
        top_topics=[
            TrendingTopic(
                title="测试话题1",
                platforms=["weibo", "douyin"],
                platforms_name=["微博", "抖音"],
                platform_count=2,
                best_rank=1,
                avg_rank=1.5,
                heat_score=95.5,
                categories={"tech", "news"}
            )
        ],
        trending_events=[
            EventInfo(
                event_id="event_001",
                title="测试事件",
                description="这是一个测试事件描述",
                topic_count=5,
                platforms=["weibo"],
                platforms_name=["微博"],
                event_type=EventType.TECH,
                heat_score=90.0
            )
        ],
        keywords=[
            KeywordInfo(
                keyword="测试",
                count=10,
                platforms={"weibo"},
                related_topics=["测试话题1"]
            )
        ],
        category_distribution={"tech": 50, "news": 30, "other": 20},
        platform_distribution={"weibo": 60, "douyin": 40},
        statistics={"avg_heat": 75.5, "max_heat": 95.5}
    )

    # 测试生成报告
    print("\n" + "=" * 60)
    print("测试生成报告:")

    try:
        report = generator.generate_report(test_output)
        print(f"✓ 报告生成成功，长度: {len(report)} 字符")

        # 显示报告的前500个字符
        print("\n报告预览（前500字符）:")
        print(report[:500] + "...\n")

    except Exception as e:
        print(f"✗ 生成报告失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 测试增强版报告
    print("\n" + "=" * 60)
    print("测试增强版报告:")

    from core.models import TrendingTopicEnhanced, KeywordInfoEnhanced, EventInfoEnhanced

    test_enhanced_output = AnalysisOutputEnhanced(
        output_time="2026-04-10 14:30:00",
        data_time_range="2026-04-09 至 2026-04-10",
        total_topics=100,
        top_topics=[
            TrendingTopicEnhanced(
                title="测试话题1",
                platforms=["weibo", "douyin"],
                platforms_name=["微博", "抖音"],
                platform_count=2,
                best_rank=1,
                avg_rank=1.5,
                heat_score=95.5,
                categories={"tech", "news"},
                keywords=["测试", "AI"]
            )
        ],
        trending_events=[
            EventInfoEnhanced(
                event_id="event_001",
                title="测试事件",
                description="这是一个测试事件描述",
                topic_count=5,
                platforms=["weibo"],
                platforms_name=["微博"],
                event_type=EventType.TECH,
                heat_score=90.0,
                confidence=0.95,
                cluster_id=1
            )
        ],
        keywords=[
            KeywordInfoEnhanced(
                keyword="测试",
                count=10,
                platforms={"weibo"},
                related_topics=["测试话题1"],
                weight=0.8
            )
        ],
        category_distribution={"tech": 50, "news": 30, "other": 20},
        platform_distribution={"weibo": 60, "douyin": 40},
        statistics={"avg_heat": 75.5, "max_heat": 95.5},
        analysis_method="nlp"
    )

    try:
        enhanced_report = generator.generate_report(test_enhanced_output)
        print(f"✓ 增强版报告生成成功，长度: {len(enhanced_report)} 字符")

        # 显示报告的前500个字符
        print("\n增强版报告预览（前500字符）:")
        print(enhanced_report[:500] + "...\n")

    except Exception as e:
        print(f"✗ 生成增强版报告失败: {e}")
        import traceback
        traceback.print_exc()

    # 测试便捷函数
    print("\n" + "=" * 60)
    print("测试便捷函数:")

    try:
        report = generate_analysis_report(test_output)
        print(f"✓ 便捷函数生成报告成功")

    except Exception as e:
        print(f"✗ 便捷函数测试失败: {e}")

    print("\n" + "=" * 60)
    print("测试完成!")
