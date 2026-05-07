# core/models.py
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Set
from enum import Enum
from pathlib import Path
from datetime import datetime
import json
from config.settings import get_settings



class EventType(Enum):
    """事件类型枚举（仅用于非 LLM 分类的内部逻辑）"""
    POLITICS = "politics"
    ECONOMY = "economy"
    TECH = "tech"
    ENTERTAINMENT = "entertainment"
    SOCIETY = "society"
    INTERNATIONAL = "international"
    SPORTS = "sports"
    OTHER = "other"

    @property
    def cn(self) -> str:
        """返回中文分类名"""
        return EVENT_TYPE_CN_MAP.get(self.value, self.value)


# 分类中英文映射
CATEGORY_CN_MAP = {
    "news": "新闻",
    "entertainment": "娱乐",
    "finance": "财经",
    "tech": "科技",
    "social": "社会",
    "politics": "政治",
    "economy": "经济",
    "international": "国际",
    "sports": "体育",
    "other": "其他",
    "internet": "互联网",
}


# 事件类型中英文映射
EVENT_TYPE_CN_MAP = {
    "politics": "政治",
    "economy": "经济",
    "tech": "科技",
    "entertainment": "娱乐",
    "society": "社会",
    "international": "国际",
    "sports": "体育",
    "other": "其他",
}


# 事件类型配置：键、中文名、主题色、图标（供报告生成器使用）
EVENT_TYPE_CONFIG = [
    ('politics',       '政治', '#e74c3c', '🏛️'),
    ('economy',        '经济', '#e67e22', '💰'),
    ('tech',           '科技', '#2980b9', '🔬'),
    ('entertainment',  '娱乐', '#8e44ad', '🎬'),
    ('sports',         '体育', '#27ae60', '⚽'),
    ('society',        '社会', '#16a085', '🌐'),
    ('international',  '国际', '#2c3e50', '🌍'),
    ('other',          '其他', '#7f8c8d', '📌'),
]

EVENT_TYPE_CONFIG_MAP = {k: (cn, color, icon) for k, cn, color, icon in EVENT_TYPE_CONFIG}

# 预定义颜色池，用于动态分配未知类别的颜色
_DYNAMIC_COLORS = [
    '#e74c3c', '#e67e22', '#2980b9', '#8e44ad', '#27ae60',
    '#16a085', '#2c3e50', '#d35400', '#c0392b', '#7f8c8d',
    '#1abc9c', '#3498db', '#9b59b6', '#f39c12', '#2ecc71',
]


def get_event_type_style(category: str) -> tuple:
    """
    获取事件类型的展示样式（中文名, 颜色, 图标）

    对于预定义类型返回固定样式，未知类型通过哈希分配颜色。
    """
    cn = EVENT_TYPE_CN_MAP.get(category, category)
    if category in EVENT_TYPE_CONFIG_MAP:
        _, color, icon = EVENT_TYPE_CONFIG_MAP[category]
        return (cn, color, icon)
    color_idx = hash(category) % len(_DYNAMIC_COLORS)
    return (cn, _DYNAMIC_COLORS[color_idx], '\U0001f4cc')


# 热度排名对应的颜色梯度（从最热到最冷，不含灰色）
_HEAT_RANK_COLORS = [
    '#ff4757',  # 第1  热红
    '#ff6348',  # 第2  橙红
    '#ffa502',  # 第3  琥珀
    '#ff9f43',  # 第4  暖橙
    '#2ed573',  # 第5  翠绿
    '#1dd1a1',  # 第6  青绿
    '#00d2d3',  # 第7  青蓝
    '#54a0ff',  # 第8  天蓝
    '#5f27cd',  # 第9  紫色
    '#c44569',  # 第10 玫红
    '#e15f41',  # 第11 赭红
    '#f8a5c2',  # 第12 粉红
    '#63cdda',  # 第13 浅青
    '#cf6a87',  # 第14 淡玫
    '#786fa6',  # 第15 灰紫
]


def heat_rank_color(rank: int, total: int) -> str:
    """
    根据热度排名返回对应颜色。

    rank=1（最热）返回红色，越往后颜色越冷，但不含灰色。

    Args:
        rank: 排名（从1开始）
        total: 总数

    Returns:
        十六进制颜色值
    """
    if total <= 1:
        return _HEAT_RANK_COLORS[0]
    ratio = (rank - 1) / (total - 1)  # 0 ~ 1
    idx = int(ratio * (len(_HEAT_RANK_COLORS) - 1))
    idx = min(idx, len(_HEAT_RANK_COLORS) - 1)
    return _HEAT_RANK_COLORS[idx]



@dataclass
class HotSearchItem:
    """标准化后的热搜项"""
    rank: int  # 排名
    title: str  # 标题
    url: Optional[str] = None  # 链接


    def to_dict(self):
        return asdict(self)


@dataclass
class HotSearchResult:
    """热搜结果集，包含平台元信息"""
    platform_key: str  # 平台标识 (如 'weibo')
    platform_name: str  # 平台显示名 (如 '微博')
    category: str  # 平台大类
    sub_category: str  # 子类
    fetch_time: str  # 爬取时间
    requested_count: int  # 请求条数
    actual_count: int  # 实际返回条数
    max_support_count: int  # 平台最大支持条数
    items: List[HotSearchItem]  # 热搜列表

    def to_dict(self):
        return {
            'metadata': {
                'platform': self.platform_key,
                'platform_name': self.platform_name,
                'category': self.category,
                'sub_category': self.sub_category,
                'fetch_time': self.fetch_time,
                'requested_count': self.requested_count,
                'actual_count': self.actual_count,
                'max_support_count': self.max_support_count,
            },
            'items': [item.to_dict() for item in self.items]
        }

    def _get_data_path(self) -> Path:
        """热搜数据保存路径 默认缓存"""
        settings = get_settings()
        output_dir = settings.get_data_dir(self.platform_key, 'HotSearchResult')
        filename = settings.get_data_filename(self.platform_key, 'HotSearchResult')
        filepath = output_dir / filename
        return filepath

    def save_to_output(self):
        """保存结果"""
        filepath = self._get_data_path()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


# ==================== 分析模块共享数据类 ====================

@dataclass
class TrackedKeywordMatch:
    """关键词追踪的单条匹配结果"""
    title: str = ""
    platform_name: str = ""
    rank: int = 0
    url: str = ""
    is_new: bool = False


@dataclass
class TrackedKeywordResult:
    """单个追踪关键词及其匹配结果（支持同义词合并）"""
    keyword: str = ""                    # 展示名（如"美国/特朗普"）
    group: str = ""                      # 所属分组名，空字符串表示未分组
    keywords: List[str] = field(default_factory=list)  # 同义词列表（合并匹配用）
    match_count: int = 0
    matches: List[TrackedKeywordMatch] = field(default_factory=list)


@dataclass
class HotSearchInfo:
    """热搜信息"""
    title: str = ""
    url: str = ""
    platform: str = ""
    platform_name: str = ""
    rank: int = 0
    category: str = ""
    sub_category: str = ""
    fetch_time: str = ""
    is_new: bool = False  # 是否是新内容


@dataclass
class TrendingTopic:
    """热门话题"""
    title: str = ""
    platforms: List[str] = field(default_factory=list)
    platforms_name: List[str] = field(default_factory=list)
    platform_count: int = 0
    best_rank: int = 0
    avg_rank: float = 0.0
    heat_score: float = 0.0
    categories: Set[str] = field(default_factory=set)
    similar_titles: List[str] = field(default_factory=list)
    event_type: str = "其他"  # 事件类型（字符串，支持动态类别）
    is_new: bool = False  # 是否是新内容
    urls: List[str] = field(default_factory=list)  # 原始链接列表


@dataclass
class TrendingTopicEnhanced(TrendingTopic):
    """增强版热门话题（智能分析）"""
    keywords: List[str] = field(default_factory=list)  # 关键词
    is_new: bool = False  # 是否是新内容


@dataclass
class KeywordInfo:
    """关键词信息"""
    keyword: str = ""
    count: int = 0
    platforms: Set[str] = field(default_factory=set)
    related_topics: List[str] = field(default_factory=list)


@dataclass
class KeywordInfoEnhanced(KeywordInfo):
    """增强版关键词信息（智能分析）"""
    weight: float = 0.0  # TF-IDF 权重


@dataclass
class EventInfo:
    """事件信息"""
    event_id: str = ""
    title: str = ""
    description: str = ""
    topic_count: int = 0
    platforms: List[str] = field(default_factory=list)
    platforms_name: List[str] = field(default_factory=list)
    event_type: str = "其他"  # 事件类型（字符串，支持动态类别）
    heat_score: float = 0.0
    topics: List[TrendingTopic] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)  # 原始链接列表


@dataclass
class EventInfoEnhanced(EventInfo):
    """增强版事件信息（智能分析）"""
    confidence: float = 0.0  # 分类置信度
    cluster_id: int = 0  # 聚类ID


@dataclass
class AnalysisOutput:
    """分析输出结果（基础版）"""
    output_time: str = ""
    data_time_range: str = ""
    total_topics: int = 0
    top_topics: List[TrendingTopic] = field(default_factory=list)
    trending_events: List[EventInfo] = field(default_factory=list)
    keywords: List[KeywordInfo] = field(default_factory=list)
    category_distribution: Dict[str, int] = field(default_factory=dict)
    platform_distribution: Dict[str, int] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)

    def _build_output_data(self, analysis_method: str = 'basic') -> dict:
        """构建输出数据（公共方法）"""
        output_data = {
            'metadata': {
                'output_time': self.output_time,
                'data_time_range': self.data_time_range,
                'total_topics': self.total_topics,
                'analysis_method': analysis_method
            },
            'top_topics': [
                {
                    'title': t.title,
                    'platforms': t.platforms,
                    'platforms_name': t.platforms_name,
                    'platform_count': t.platform_count,
                    'best_rank': t.best_rank,
                    'avg_rank': round(t.avg_rank, 2),
                    'heat_score': round(t.heat_score, 2),
                    'categories': list(t.categories),
                    'event_type': t.event_type or '其他',
                    **({'keywords': t.keywords} if hasattr(t, 'keywords') and t.keywords else {}),
                    **({'urls': t.urls} if hasattr(t, 'urls') and t.urls else {}),
                }
                for t in self.top_topics
            ],
            'trending_events': [
                {
                    'event_id': e.event_id,
                    'title': e.title,
                    'description': e.description,
                    'topic_count': e.topic_count,
                    'platforms': e.platforms,
                    'platforms_name': e.platforms_name,
                    'event_type': e.event_type or '其他',
                    **({'confidence': round(e.confidence, 2)} if hasattr(e, 'confidence') else {}),
                    'heat_score': round(e.heat_score, 2),
                    'topics': [t.title for t in e.topics],
                    **({'cluster_id': e.cluster_id} if hasattr(e, 'cluster_id') else {}),
                    **({'urls': e.urls} if hasattr(e, 'urls') and e.urls else {}),
                }
                for e in self.trending_events
            ],
            'keywords': [
                {
                    'keyword': k.keyword,
                    **({'weight': round(k.weight, 4)} if hasattr(k, 'weight') else {}),
                    'count': k.count,
                    'platforms': list(k.platforms),
                    'related_topics': k.related_topics[:3]
                }
                for k in self.keywords
            ],
            'category_distribution': self.category_distribution,
            'platform_distribution': self.platform_distribution,
            'statistics': self.statistics,
            **(
                {'tracked_keywords': [
                    {
                        'keyword': tk.keyword,
                        'group': tk.group,
                        'keywords': tk.keywords,
                        'match_count': tk.match_count,
                        'matches': [
                            {
                                'title': m.title,
                                'platform_name': m.platform_name,
                                'rank': m.rank,
                                'url': m.url,
                                'is_new': m.is_new,
                            }
                            for m in tk.matches
                        ]
                    }
                    for tk in self.tracked_keywords
                ]}
                if hasattr(self, 'tracked_keywords') and self.tracked_keywords else {}
            ),
        }
        return output_data

    def _get_default_output_dir(self) -> Path:
        """获取默认输出目录"""
        settings = get_settings()
        output_dir = settings.paths.BASE_DIR / "outputs"
        output_dir.mkdir(exist_ok=True)
        return output_dir

    def save(self, output_file: str = None) -> str:
        """保存分析结果"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self._get_default_output_dir() / f"hotsearch_output_{timestamp}.json"

        output_data = self._build_output_data(analysis_method='basic')

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        return str(output_file)

    def save_as_html(self, output_file: str = None) -> str:
        """保存分析结果为HTML格式"""
        from utils.html_report_generator import HtmlReportGenerator

        generator = HtmlReportGenerator()
        return generator.generate(self, output_file)

    def save_as_email(self, output_file: str = None) -> str:
        """保存分析结果为邮件兼容HTML格式"""
        from utils.email_report_generator import EmailReportGenerator

        generator = EmailReportGenerator()
        return generator.generate(self, output_file)

    def save_as_markdown(self, output_file: str = None) -> str:
        """保存分析结果为Markdown格式"""
        from utils.md_report_generator import ReportGenerator

        generator = ReportGenerator()
        report = generator.generate_report(self)

        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = self._get_default_output_dir()
            output_file = output_dir / f"hotsearch_report_{timestamp}.md"
        else:
            output_file = Path(output_file)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        return str(output_file)


@dataclass
class AnalysisOutputEnhanced(AnalysisOutput):
    """增强版分析输出结果（智能分析）"""
    analysis_method: str = "nlp"  # 分析方法：nlp 或 basic
    tracked_keywords: List[TrackedKeywordResult] = field(default_factory=list)  # 关键词追踪结果

    def save(self, output_file: str = None) -> str:
        """保存增强版分析结果"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self._get_default_output_dir() / f"hotsearch_output_{timestamp}.json"

        output_data = self._build_output_data(analysis_method=self.analysis_method)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        return str(output_file)

    def save_as_html(self, output_file: str = None) -> str:
        """保存增强版分析结果为HTML格式"""
        from utils.html_report_generator import HtmlReportGenerator

        generator = HtmlReportGenerator()
        return generator.generate(self, output_file)

    def save_as_email(self, output_file: str = None) -> str:
        """保存增强版分析结果为邮件兼容HTML格式"""
        from utils.email_report_generator import EmailReportGenerator

        generator = EmailReportGenerator()
        return generator.generate(self, output_file)

    def save_as_markdown(self, output_file: str = None) -> str:
        """保存增强版分析结果为Markdown格式"""
        from utils.md_report_generator import ReportGenerator

        generator = ReportGenerator()
        report = generator.generate_report(self)

        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = self._get_default_output_dir() / 'analysis'
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / f"hotsearch_report_{timestamp}.md"
        else:
            output_file = Path(output_file)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        return str(output_file)