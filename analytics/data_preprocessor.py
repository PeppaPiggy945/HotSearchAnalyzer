# analytics/data_preprocessor.py
"""
AI 洞察数据预处理模块

在发送给大模型 API 之前，利用本地 NLP 能力对热搜数据进行预处理：
1. 按事件聚类合并，消除跨平台重复标题
2. 计算热度评分并过滤低热度噪音
3. 提取排名趋势（跨天排名变化序列）
4. 将低热度事件压缩为统计摘要

目标：在保留完整分析价值的前提下，将 token 消耗降低 50-70%，
     同时支持更长的时间跨度（7-14 天）。
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger
from core.config_manager import ConfigManager

logger = get_logger(__name__)


class InsightDataPreprocessor:
    """AI 洞察数据预处理器"""

    def __init__(self):
        self._config = self._load_config()
        # 预处理参数（带默认值）
        pre_cfg = self._config.get("preprocessing", {})
        self.enabled = pre_cfg.get("enabled", True)
        self.min_heat_score = pre_cfg.get("min_heat_score", 10)
        self.max_events_detail = pre_cfg.get("max_events_detail", 40)
        self.similarity_threshold = pre_cfg.get("similarity_threshold", 0.55)

    @staticmethod
    def _load_config() -> dict:
        try:
            return ConfigManager().user_config.get("ai_insight", {})
        except Exception:
            return {}

    # ------------------------------------------------------------------
    #  公开接口
    # ------------------------------------------------------------------

    def preprocess(
        self,
        raw_data: list,
        days: int = 1,
    ) -> Tuple[list, Dict[str, Any]]:
        """
        对 DataReader 输出的原始数据进行预处理。

        Args:
            raw_data: DataReader.load_data() 解析后的列表，
                      格式 [{"s": "平台名", "d": [[rank, title, date], ...]}, ...]
            days: 数据跨度天数（影响趋势分析逻辑）

        Returns:
            (processed_data, metadata)
            - processed_data: 预处理后的结构化数据列表（可直接 JSON 序列化）
            - metadata: 预处理统计信息
        """
        if not self.enabled or not raw_data:
            return raw_data, {"preprocessing": False, "reason": "未启用或无数据"}

        # 1. 扁平化为统一格式
        flat_items = self._flatten(raw_data)
        if not flat_items:
            return raw_data, {"preprocessing": False, "reason": "扁平化后无数据"}

        total_raw = len(flat_items)
        logger.info(f"开始预处理: {total_raw} 条原始记录, {days} 天跨度")

        # 2. 按事件聚类合并（跨平台去重）
        events = self._cluster_by_event(flat_items)
        total_events = len(events)
        logger.info(f"聚类完成: {total_raw} 条 -> {total_events} 个事件")

        # 3. 计算热度分数
        self._calculate_heat(events)
        filtered = self._filter_by_heat(events)
        removed = total_events - len(filtered)
        if removed > 0:
            logger.info(f"热度过滤: 移除 {removed} 个低热度事件, 保留 {len(filtered)} 个")

        # 4. 构建排名趋势
        self._build_rank_trends(filtered, days)

        # 5. 分层输出：高热度详情 + 低热度摘要
        sorted_events = sorted(filtered, key=lambda e: e["heat_score"], reverse=True)
        detail_events = sorted_events[: self.max_events_detail]
        summary_events = sorted_events[self.max_events_detail :]

        # 构建输出
        processed = self._build_output(detail_events, summary_events)

        # 统计信息
        all_dates = sorted({item["date"] for item in flat_items})
        metadata = {
            "preprocessing": True,
            "raw_records": total_raw,
            "total_events": total_events,
            "after_filter": len(filtered),
            "detail_events": len(detail_events),
            "summary_events": len(summary_events),
            "date_range": f"{all_dates[0]} ~ {all_dates[-1]}" if all_dates else "",
            "platform_count": len({item["platform"] for item in flat_items}),
            "token_reduction_estimate": f"{(1 - len(filtered) / max(total_raw, 1)) * 100:.0f}%",
        }

        logger.info(
            f"预处理完成: 详情 {len(detail_events)} 个 + 摘要 {len(summary_events)} 个, "
            f"预估节省 token: {metadata['token_reduction_estimate']}"
        )
        return processed, metadata

    # ------------------------------------------------------------------
    #  Step 1: 扁平化
    # ------------------------------------------------------------------

    @staticmethod
    def _flatten(raw_data: list) -> List[Dict[str, Any]]:
        """将按平台分组的数据扁平化为统一列表"""
        items = []
        for platform_group in raw_data:
            platform = platform_group.get("s", "")
            for record in platform_group.get("d", []):
                if len(record) >= 3:
                    items.append({
                        "rank": record[0],
                        "title": record[1],
                        "date": record[2],
                        "platform": platform,
                    })
        return items

    # ------------------------------------------------------------------
    #  Step 2: 事件聚类（轻量级，基于标题分词重叠）
    # ------------------------------------------------------------------

    def _cluster_by_event(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """基于标题相似度将跨平台条目合并为事件"""
        # 按标题分组（完全相同的标题直接合并）
        title_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in items:
            title_groups[item["title"]].append(item)

        # 初始化词集缓存
        word_cache: Dict[str, set] = {}
        for title in title_groups:
            word_cache[title] = self._tokenize(title)

        # 贪心合并相似标题组
        merged: List[Dict[str, List[Dict[str, Any]]]] = []  # [(representative_title, [items])]
        used_titles: set = set()

        # 按组大小降序（覆盖面广的先处理）
        sorted_titles = sorted(title_groups.keys(), key=lambda t: -len(title_groups[t]))

        for title in sorted_titles:
            if title in used_titles:
                continue
            group_items = list(title_groups[title])
            used_titles.add(title)

            # 寻找相似标题并合并
            for other_title in sorted_titles:
                if other_title in used_titles:
                    continue
                if self._is_similar(word_cache[title], word_cache[other_title]):
                    group_items.extend(title_groups[other_title])
                    used_titles.add(other_title)

            merged.append({"title": title, "items": group_items})

        # 转换为事件字典
        events = []
        for group in merged:
            items_list = group["items"]
            platforms = list({it["platform"] for it in items_list})
            titles = list({it["title"] for it in items_list})
            ranks = [it["rank"] for it in items_list if it["rank"] > 0]
            dates = sorted({it["date"] for it in items_list})

            events.append({
                "title": group["title"],
                "titles": titles,          # 所有变体标题
                "platforms": platforms,
                "platform_count": len(platforms),
                "best_rank": min(ranks) if ranks else 99,
                "avg_rank": sum(ranks) / len(ranks) if ranks else 99,
                "records": items_list,      # 保留原始记录用于趋势分析
                "dates": dates,
                "heat_score": 0.0,
            })

        return events

    # ------------------------------------------------------------------
    #  Step 3: 热度计算与过滤
    # ------------------------------------------------------------------

    def _calculate_heat(self, events: List[Dict[str, Any]]) -> None:
        """为每个事件计算热度分数（基于爬取深度的加权归一化）"""
        if not events:
            return

        # 统计各平台爬取条数，用于加权（爬取越少越"精选"，权重越高）
        platform_items_count: Dict[str, int] = defaultdict(int)
        for e in events:
            for r in e.get("records", []):
                platform_items_count[r["platform"]] += 1

        total_weight = sum(1.0 / c for c in platform_items_count.values()) if platform_items_count else 1.0

        for e in events:
            title_variety = min(len(e["titles"]) - 1, 5)
            date_span = len(e["dates"])
            weighted_coverage = sum(
                1.0 / platform_items_count.get(p, 1) for p in e["platforms"]
            )
            normalized = weighted_coverage / total_weight

            e["heat_score"] = (
                normalized * 40                              # 跨平台覆盖（加权归一化）
                + max(0, (1 - (e["best_rank"] / 10))) * 25   # 排名优势
                + min(title_variety * 8, 15)                 # 标题变体
                + min(date_span * 5, 20)                     # 持续天数
            )

    def _filter_by_heat(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤低热度事件"""
        return [e for e in events if e["heat_score"] >= self.min_heat_score]

    # ------------------------------------------------------------------
    #  Step 4: 排名趋势
    # ------------------------------------------------------------------

    @staticmethod
    def _build_rank_trends(events: List[Dict[str, Any]], days: int) -> None:
        """为每个事件构建跨天排名趋势序列"""
        for event in events:
            trend = {}
            for record in event["records"]:
                date = record["date"]
                rank = record["rank"]
                if date not in trend or rank < trend[date]:
                    trend[date] = rank  # 同天取最佳排名
            sorted_dates = sorted(trend.keys())
            event["rank_trend"] = {
                "dates": sorted_dates,
                "ranks": [trend[d] for d in sorted_dates],
            }
            # 判断趋势方向
            ranks = event["rank_trend"]["ranks"]
            if len(ranks) >= 2:
                if ranks[-1] < ranks[0]:
                    event["trend_direction"] = "上升"
                elif ranks[-1] > ranks[0]:
                    event["trend_direction"] = "下降"
                else:
                    event["trend_direction"] = "稳定"
            else:
                event["trend_direction"] = "新出现" if len(ranks) == 1 else "未知"

    # ------------------------------------------------------------------
    #  Step 5: 构建输出
    # ------------------------------------------------------------------

    def _build_output(
        self,
        detail_events: List[Dict[str, Any]],
        summary_events: List[Dict[str, Any]],
    ) -> list:
        """构建最终输出数据（分层结构，key 缩写以节省 token）"""
        output = []

        # --- 高热度事件：详细信息 ---
        if detail_events:
            detail_list = []
            for e in detail_events:
                rt = e.get("rank_trend", {})
                entry = {
                    "tt": e["title"],
                    "pf": e["platforms"],
                    "pc": e["platform_count"],
                    "br": e["best_rank"],
                    "hs": round(e["heat_score"], 1),
                    "tr": e.get("trend_direction", "未知"),
                    "rt": {"dt": rt.get("dates", []), "rk": rt.get("ranks", [])},
                    "dt": e["dates"],
                }
                # 保留代表性变体标题（最多3个）
                if len(e["titles"]) > 1:
                    entry["tv"] = [t for t in e["titles"] if t != e["title"]][:3]
                detail_list.append(entry)
            output.append({"tp": "hh", "n": len(detail_list), "ev": detail_list})

        # --- 低热度事件：统计摘要 ---
        if summary_events:
            cat_counter: Dict[str, int] = defaultdict(int)
            for e in summary_events:
                cat_counter["其他"] += 1

            output.append({
                "tp": "ls",
                "n": len(summary_events),
                "cd": dict(cat_counter),
                "st": [e["title"] for e in summary_events[:10]],
            })

        return output

    # ------------------------------------------------------------------
    #  文本处理工具
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> set:
        """轻量级分词（中文按字符 bigram + 英文按空格）"""
        try:
            import jieba
            return set(jieba.cut(text))
        except ImportError:
            import re
            return set(re.findall(r'[\w]+', text))

    def _is_similar(self, words1: set, words2: set) -> bool:
        """判断两组词是否属于同一事件"""
        if not words1 or not words2:
            return False
        inter, union = len(words1 & words2), len(words1 | words2)
        jaccard = inter / union if union > 0 else 0.0
        if jaccard >= self.similarity_threshold:
            return True
        return len(words1 & words2) >= 3
