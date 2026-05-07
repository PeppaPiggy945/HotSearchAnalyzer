# analytics/event_clusterer.py
"""
事件聚类模块
使用策略模式将话题聚合为事件，支持 KMeans（NLP）和贪心相似度（基础）两种策略。
"""

import hashlib
from datetime import datetime
from typing import Callable, Dict, List, Optional
from abc import ABC, abstractmethod
from collections import defaultdict

from core.models import TrendingTopicEnhanced, EventInfoEnhanced

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False

# 最大单事件话题数
MAX_CLUSTER_SIZE = 15


# ------------------------------------------------------------------
#  Helpers
# ------------------------------------------------------------------

def _stable_event_id(title: str) -> str:
    """基于 MD5 的跨运行稳定事件 ID"""
    h = hashlib.md5(title.encode('utf-8')).hexdigest()
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"event_{ts}_{h[:8]}"


def create_event(topics: List[TrendingTopicEnhanced], cluster_id: int) -> EventInfoEnhanced:
    """从话题列表创建事件（公共工具函数）"""
    top = max(topics, key=lambda x: x.heat_score)
    titles = [t.title for t in topics]
    desc = f"包含 {len(topics)} 个相关话题：" + "、".join(titles[:3])
    if len(titles) > 3:
        desc += f" 等{len(topics)}个话题"

    all_plat: List[str] = []
    all_plat_name: List[str] = []
    all_urls: List[str] = []
    for t in topics:
        for p in t.platforms:
            if p not in all_plat:
                all_plat.append(p)
        for pn in t.platforms_name:
            if pn not in all_plat_name:
                all_plat_name.append(pn)
        for u in t.urls:
            if u and u not in all_urls:
                all_urls.append(u)

    return EventInfoEnhanced(
        event_id=_stable_event_id(top.title[:50]),
        title=top.title[:50],
        description=desc,
        topic_count=len(topics),
        platforms=all_plat,
        platforms_name=all_plat_name,
        event_type="其他",
        confidence=0.0,
        heat_score=float(sum(t.heat_score for t in topics)),
        topics=topics,
        cluster_id=int(cluster_id),
        urls=all_urls,
    )


def split_oversized(topics: List[TrendingTopicEnhanced], max_size: int,
                    is_same_fn: Callable[[str, str], bool]) -> List[EventInfoEnhanced]:
    """对过大集群按相似度二次拆分为多个事件"""
    events: List[EventInfoEnhanced] = []
    sorted_topics = sorted(topics, key=lambda x: x.heat_score, reverse=True)
    used: set = set()

    for i, topic in enumerate(sorted_topics):
        if topic.title in used:
            continue
        group = [topic]
        used.add(topic.title)
        for other in sorted_topics[i + 1:]:
            if other.title in used or len(group) >= max_size:
                continue
            if is_same_fn(topic.title, other.title):
                group.append(other)
                used.add(other.title)
        events.append(create_event(group, -1))
    return events


# ------------------------------------------------------------------
#  Strategies
# ------------------------------------------------------------------

class ClusteringStrategy(ABC):
    """聚类策略抽象基类"""

    @abstractmethod
    def group(self, topics: List[TrendingTopicEnhanced]) -> List[List[TrendingTopicEnhanced]]:
        """将话题分组，每组对应一个事件"""
        ...


class GreedyClusteringStrategy(ClusteringStrategy):
    """贪心相似度聚类（基础模式）"""

    def __init__(self, is_same_fn: Callable[[str, str], bool], max_size: int = MAX_CLUSTER_SIZE):
        self._is_same = is_same_fn
        self._max_size = max_size

    def group(self, topics: List[TrendingTopicEnhanced]) -> List[List[TrendingTopicEnhanced]]:
        groups: List[List[TrendingTopicEnhanced]] = []
        used: set = set()
        sorted_topics = sorted(topics, key=lambda x: x.heat_score, reverse=True)

        for i, topic in enumerate(sorted_topics):
            if topic.title in used:
                continue
            group = [topic]
            used.add(topic.title)
            for other in sorted_topics[i + 1:]:
                if other.title in used or len(group) >= self._max_size:
                    break
                if self._is_same(topic.title, other.title):
                    group.append(other)
                    used.add(other.title)
            groups.append(group)
        return groups


class KMeansClusteringStrategy(ClusteringStrategy):
    """KMeans + TF-IDF 聚类（NLP 模式），过大集群自动拆分"""

    def __init__(self, is_same_fn: Callable[[str, str], bool], max_size: int = MAX_CLUSTER_SIZE):
        self._is_same = is_same_fn
        self._max_size = max_size

    def group(self, topics: List[TrendingTopicEnhanced]) -> List[List[TrendingTopicEnhanced]]:
        if not NLP_AVAILABLE or len(topics) < 3:
            return GreedyClusteringStrategy(self._is_same, self._max_size).group(topics)

        try:
            texts = [t.title for t in topics]
            vectorizer = TfidfVectorizer(max_features=50, min_df=1)
            matrix = vectorizer.fit_transform(texts)

            n = max(len(topics) // 5, 8)
            n = min(n, len(topics) // 2)
            n = max(n, 3)

            clusters = KMeans(n_clusters=n, random_state=42, n_init=10).fit_predict(matrix)
            cluster_dict: Dict[int, list] = defaultdict(list)
            for topic, cid in zip(topics, clusters):
                cluster_dict[cid].append(topic)

            groups: List[List[TrendingTopicEnhanced]] = []
            for topic_list in cluster_dict.values():
                if len(topic_list) > self._max_size:
                    sub = split_oversized(topic_list, self._max_size, self._is_same)
                    groups.extend([e.topics for e in sub])
                else:
                    groups.append(topic_list)
            return groups
        except Exception:
            return GreedyClusteringStrategy(self._is_same, self._max_size).group(topics)


# ------------------------------------------------------------------
#  Clusterer
# ------------------------------------------------------------------

class EventClusterer:
    """事件聚类器，使用可插拔策略将话题聚合为事件"""

    def __init__(self, strategy: ClusteringStrategy):
        self._strategy = strategy

    def cluster(self, topics: List[TrendingTopicEnhanced]) -> List[EventInfoEnhanced]:
        groups = self._strategy.group(topics)
        return [create_event(group, i) for i, group in enumerate(groups)]
