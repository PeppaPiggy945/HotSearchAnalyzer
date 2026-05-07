# analytics/llm_middleware.py
"""
LLM 中间处理模块 — 聚类校验、代表标题选取、事件摘要生成

利用轻量本地模型在数据中间阶段参与处理：
1. ValidateClustersStep: 检查 KMeans 聚类是否混入不相关话题，拆分污染事件
2. PickRepresentativeTitleStep: 从事件的多个标题中选出最简洁准确的代表标题
3. GenerateEventSummaryStep: 为每个事件生成一句话摘要

所有步骤在 LLM 不可用或推理失败时静默回退，不影响基础功能。
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from core.logger import get_logger
from core.models import EventInfoEnhanced, TrendingTopicEnhanced
from analytics.llm_cache import LLMCache

logger = get_logger(__name__)


# ============================================================
# Prompt 模板
# ============================================================

VALIDATE_CLUSTERS_PROMPT = """你是一个文本相似度判断助手。给定一组标题，判断它们是否都围绕同一个事件/话题。
- 如果所有标题都在讨论同一件事，返回"是"
- 如果有标题明显不相关（讨论完全不同的事），返回"否"
- 只返回"是"或"否"，不要返回其他内容

标题列表：
{titles}"""

PICK_TITLE_PROMPT = """从以下标题列表中选择最能概括该事件的一个标题作为代表标题。
规则：
- 选择信息量最大、最简洁准确的一个
- 优先选择不含营销话术、感叹号、emoji的客观标题
- 只返回选中的标题原文，不要修改或添加任何内容

标题列表：
{titles}

代表标题："""

# ============================================================
# LLM 推理包装
# ============================================================

class LLMInference:
    """复用 LLMEventClassifier 的模型实例进行推理"""

    _instance = None

    @classmethod
    def get_model(cls):
        """获取全局 LLM 分类器实例（复用已加载的模型）"""
        if cls._instance is None:
            try:
                from analytics.llm_classifier import get_classifier
                cls._instance = get_classifier()
            except Exception:
                pass
        return cls._instance

    @classmethod
    def infer(cls, system_prompt: str, user_prompt: str, max_tokens: int = 50) -> str:
        """
        调用 LLM 进行推理，失败返回空字符串。
        """
        classifier = cls.get_model()
        if classifier is None or not classifier.enabled:
            return ""

        try:
            return classifier._infer_raw(system_prompt, user_prompt, max_tokens)
        except Exception as e:
            logger.debug(f"LLM 推理失败: {e}")
            return ""

    @classmethod
    def infer_batch(cls, system_prompt: str, user_prompts: List[str],
                    max_tokens: int = 10) -> List[str]:
        """
        批量推理：多条 prompt 打包为一条 API 请求。

        仅 API 模式下有效（本地模式回退为逐条调用）。
        返回与 user_prompts 等长的结果列表。
        """
        classifier = cls.get_model()
        if classifier is None or not classifier.enabled:
            return [""] * len(user_prompts)

        try:
            if classifier.mode == "api" and classifier.api_base_url:
                return classifier._infer_api_batch(system_prompt, user_prompts, max_tokens)
            # 本地模式回退
            return [cls.infer(system_prompt, p, max_tokens) for p in user_prompts]
        except Exception as e:
            logger.debug(f"LLM 批量推理失败: {e}")
            return [""] * len(user_prompts)


# ============================================================
# 功能实现
# ============================================================

def _validate_cluster(titles: List[str]) -> bool:
    """
    判断一组标题是否都在讨论同一事件。
    返回 True 表示相关（保持原聚类），False 表示不相关（需要拆分）。
    """
    if len(titles) <= 2:
        return True

    text_block = "\n".join(f"- {t}" for t in titles[:8])
    user_prompt = f"标题列表：\n{text_block}"

    response = LLMInference.infer(VALIDATE_CLUSTERS_PROMPT, user_prompt, max_tokens=5)
    if not response:
        return True

    return "否" not in response.strip()[:5]


def _validate_clusters_batch(title_groups: List[List[str]]) -> List[bool]:
    """
    批量校验多组标题的相关性。
    返回列表，True 表示该组相关，False 表示需拆分。
    """
    results = []
    prompts = []
    indices = []  # 需要实际调用 LLM 的索引

    for i, titles in enumerate(title_groups):
        if len(titles) <= 2:
            results.append(True)
            continue
        results.append(True)  # 默认值，LLM 失败时回退
        indices.append(i)
        text_block = "\n".join(f"- {t}" for t in titles[:8])
        prompts.append(f"标题列表：\n{text_block}")

    if not prompts:
        return results

    # 模型单次输出太短（只返回"是/否"），打包意义不大，
    # 但仍可通过合并请求减少 system_prompt 重复
    # 用批量推理接口统一调用
    responses = LLMInference.infer_batch(VALIDATE_CLUSTERS_PROMPT, prompts, max_tokens=len(prompts) * 5 + 20)
    for idx, resp in zip(indices, responses):
        if resp:
            results[idx] = "否" not in resp.strip()[:5]

    return results


def _pick_representative_title(titles: List[str]) -> str:
    """
    从一组标题中选出最具代表性的一个。
    失败时回退为热度最高的标题。
    """
    if not titles:
        return ""
    if len(titles) == 1:
        return titles[0]

    text_block = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles[:10]))
    user_prompt = f"标题列表：\n{text_block}\n\n代表标题："

    response = LLMInference.infer(PICK_TITLE_PROMPT, user_prompt, max_tokens=50)
    if not response:
        return titles[0]

    # 清理输出
    result = response.strip().rstrip("。.！!").strip()
    result = re.sub(r'^(\d+[.、:：]\s*)', '', result)

    if result and len(result) <= 80:
        return result
    return titles[0]


# ============================================================
# Pipeline Steps
# ============================================================

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from analytics.pipeline import AnalysisContext


class _MiddlewareStep(ABC):
    """中间处理步骤基类（避免与 pipeline.py 循环导入）"""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def execute(self, ctx: 'AnalysisContext') -> None:
        ...


class ValidateClustersStep(_MiddlewareStep):
    """
    Step: 聚类校验 — 用 LLM 检查每个事件的话题是否真的相关。
    对不相关的话题进行拆分，拆分后的小事件会被重新创建。
    LLM 不可用时跳过（保持原聚类结果）。
    """

    def __init__(self):
        self._cache = LLMCache("middleware_validate", result_key="r")

    def execute(self, ctx: AnalysisContext) -> None:
        if LLMInference.get_model() is None:
            print("    跳过聚类校验（LLM 不可用）")
            return

        events = ctx.events
        if not events:
            return

        before = len(events)
        new_events: List[EventInfoEnhanced] = []
        split_count = 0
        total = len(events)

        for i, event in enumerate(events, 1):
            titles = [t.title for t in event.topics]
            if len(titles) <= 1:
                new_events.append(event)
                continue

            # 构建缓存键
            cache_key = LLMCache.make_key("、".join(sorted(set(titles))))
            cached = self._cache.get(cache_key)
            if cached == "ok":
                new_events.append(event)
                continue

            # LLM 校验
            if _validate_cluster(titles):
                self._cache.put(cache_key, "ok")
                new_events.append(event)
            else:
                # 拆分：每个话题独立成事件
                logger.info(f"聚类拆分: 「{event.title}」包含不相关话题，拆分为 {len(titles)} 个事件")
                for topic in event.topics:
                    from analytics.event_clusterer import create_event
                    sub_event = create_event([topic], -1)
                    new_events.append(sub_event)
                split_count += 1

            if i % 20 == 0 or i == total:
                print(f"    聚类校验进度: {i}/{total}")

        if split_count > 0:
            self._cache.save()
            # 重新计算 cluster_id
            for i, ev in enumerate(new_events):
                ev.cluster_id = i
            ctx.events = new_events
            print(f"    聚类校验: {before} → {len(new_events)} "
                  f"(拆分 {split_count} 个污染聚类)")


class PickRepresentativeTitleStep(_MiddlewareStep):
    """
    Step: 代表标题选取 — 用 LLM 从每个事件的多个标题中选出最简洁准确的代表标题。
    LLM 不可用时跳过（保持热度最高的标题）。
    """

    def __init__(self):
        self._cache = LLMCache("middleware_title", result_key="r")

    def execute(self, ctx: AnalysisContext) -> None:
        if LLMInference.get_model() is None:
            print("    跳过代表标题选取（LLM 不可用）")
            return

        events = ctx.events
        if not events:
            return

        picked = 0
        total = len(events)
        for i, event in enumerate(events, 1):
            titles = [t.title for t in event.topics]
            if len(titles) <= 1:
                continue

            cache_key = LLMCache.make_key("、".join(sorted(set(titles))))
            cached = self._cache.get(cache_key)
            if cached:
                event.title = cached
                picked += 1
                continue

            new_title = _pick_representative_title(titles)
            if new_title and new_title != event.title:
                event.title = new_title[:50]
                self._cache.put(cache_key, new_title[:50])
                picked += 1

            if i % 20 == 0 or i == total:
                print(f"    标题选取进度: {i}/{total}")

        if picked > 0:
            self._cache.save()
            print(f"    代表标题选取: 为 {picked}/{len(events)} 个事件选取了新标题")
