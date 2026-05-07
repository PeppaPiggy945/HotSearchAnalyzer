"""
AI 洞察报告生成模块

利用大模型 API 对热搜数据进行深度分析，生成结构化洞察报告。
将 prompt_generator 生成的高质量 Prompt 直接发送给 API，无需保存本地文件。

与 llm 分析模块的区别：
- llm 模块：用于事件分类、聚类校验等轻量级任务，支持 API/本地模型
- ai_insight 模块：用于生成完整洞察报告，仅支持 API，推荐更强模型
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from core.logger import get_logger

logger = get_logger(__name__)


class AIInsightGenerator:
    """AI 洞察报告生成器"""

    def __init__(self):
        """从 user_config.yaml 的 ai_insight 节加载配置"""
        self._config = self._load_config()
        self.enabled = self._config.get("enabled", False)

        if self.enabled:
            self.api_base_url = self._config.get("api_base_url", "")
            self.api_key = self._config.get("api_key", "")
            self.api_model = self._config.get("api_model", "")
            self.max_tokens = self._config.get("max_tokens", 8000)
            self.temperature = self._config.get("temperature", 0.7)
            self.timeout = self._config.get("timeout", 300)
            self.max_retries = self._config.get("max_retries", 2)

            report_cfg = self._config.get("report", {})
            self.output_dir = Path(report_cfg.get("output_dir", "outputs/insight"))
            self.filename_prefix = report_cfg.get("filename_prefix", "ai_insight")
        else:
            self.api_base_url = ""
            self.api_key = ""
            self.api_model = ""
            self.max_tokens = 8000
            self.temperature = 0.7
            self.timeout = 300
            self.max_retries = 2
            self.output_dir = Path("outputs/insight")
            self.filename_prefix = "ai_insight"

    @staticmethod
    def _load_config() -> dict:
        try:
            from core.config_manager import ConfigManager
            return ConfigManager().user_config.get("ai_insight", {})
        except (ImportError, AttributeError, KeyError):
            return {}

    @property
    def is_available(self) -> bool:
        """是否可用（启用且配置完整）"""
        return (self.enabled
                and bool(self.api_base_url)
                and bool(self.api_key)
                and bool(self.api_model))

    def _call_api(self, prompt: str) -> str:
        """
        调用大模型 API，带重试和超时。

        Returns:
            模型回复文本，失败返回空字符串。
        """
        import requests

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.api_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        for attempt in range(self.max_retries):
            try:
                resp = requests.post(
                    f"{self.api_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"AI 洞察 API 调用失败（已重试{self.max_retries}次）: {e}")
                    return ""
                wait = 2 ** attempt
                logger.warning(f"AI 洞察 API 请求失败，{wait}秒后重试({attempt+1}/{self.max_retries}): {e}")
                time.sleep(wait)

    def _save_report(self, content: str, prompt_type: str) -> Path:
        """将报告保存为 Markdown 文件"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.filename_prefix}_{prompt_type}_{timestamp}.md"
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return filepath

    def generate_insight(
        self,
        prompt: str,
        prompt_type: str = "分析",
        save_to_file: bool = True,
    ) -> Dict[str, Any]:
        """
        根据给定的 Prompt 生成 AI 洞察报告。

        Args:
            prompt: 完整的 Prompt 内容（通常由 prompt_generator 生成）
            prompt_type: 报告类型标识（用于文件命名，如"结构化分析"/"趋势洞察"）
            save_to_file: 是否保存到文件

        Returns:
            {
                "status": "success" | "failed" | "skipped",
                "content": "...",        # 报告内容（成功时）
                "file_path": "...",      # 保存路径（成功时）
                "error": "...",          # 错误信息（失败时）
                "elapsed": 3.14,         # 耗时秒数
            }
        """
        if not self.is_available:
            reason = "未启用" if not self.enabled else "API 配置不完整（缺少 api_base_url/api_key/api_model）"
            logger.info(f"AI 洞察报告已跳过: {reason}")
            return {"status": "skipped", "reason": reason, "elapsed": 0}

        start = time.time()
        logger.info(f"开始生成 AI 洞察报告（{prompt_type}），模型: {self.api_model}")

        try:
            content = self._call_api(prompt)
            elapsed = time.time() - start

            if not content:
                return {
                    "status": "failed",
                    "error": "API 未返回有效内容",
                    "elapsed": elapsed,
                }

            result = {
                "status": "success",
                "content": content,
                "elapsed": elapsed,
            }

            if save_to_file:
                filepath = self._save_report(content, prompt_type)
                result["file_path"] = str(filepath)
                logger.info(f"AI 洞察报告已保存: {filepath}（耗时 {elapsed:.1f}s）")

            return result

        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"AI 洞察报告生成失败: {e}")
            return {"status": "failed", "error": str(e), "elapsed": elapsed}

    def generate_all_insights(
        self,
        prompts: Optional[Dict[str, str]] = None,
        days: int = 1,
        platforms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        根据已有的 Prompt 生成 AI 洞察报告（结构化分析 + 趋势洞察）。

        推荐用法：先由 PromptGenerator 生成 prompt，再将结果传入本方法。
        若未提供 prompts，会尝试内部生成（向后兼容，但会重复加载数据）。

        Args:
            prompts: 已生成的 Prompt 字典，如 {"structural": "...", "trend": "..."}
            days: 仅在 prompts 为 None 时使用，分析最近几天的数据
            platforms: 仅在 prompts 为 None 时使用，指定平台列表

        Returns:
            {
                "structural": {...},  # 结构化分析结果
                "trend": {...},       # 趋势洞察结果
                "elapsed": 3.14,      # 总耗时
            }
        """
        start = time.time()
        results = {}

        # 如果没有传入 prompts，向后兼容：内部生成
        if prompts is None:
            logger.warning("未传入 prompts 参数，将内部生成（会导致数据重复加载，建议先调用 PromptGenerator）")
            from utils.prompt_generator import PromptGenerator
            generator = PromptGenerator()
            prompts = generator.generate_all_prompts(
                days=days, platforms=platforms, save_to_file=False,
            )

        if not prompts:
            return {"structural": {"status": "skipped", "reason": "无可用 Prompt"},
                    "trend": {"status": "skipped", "reason": "无可用 Prompt"},
                    "elapsed": 0}

        # 生成结构化分析洞察
        if prompts.get("structural"):
            try:
                results["structural"] = self.generate_insight(
                    prompts["structural"], "结构化分析", save_to_file=True
                )
            except Exception as e:
                logger.error(f"结构化分析洞察失败: {e}")
                results["structural"] = {"status": "failed", "error": str(e)}
        else:
            results["structural"] = {"status": "skipped", "reason": "Prompt 为空"}

        # 生成趋势洞察报告
        if prompts.get("trend"):
            try:
                results["trend"] = self.generate_insight(
                    prompts["trend"], "趋势洞察", save_to_file=True
                )
            except Exception as e:
                logger.error(f"趋势洞察失败: {e}")
                results["trend"] = {"status": "failed", "error": str(e)}
        else:
            results["trend"] = {"status": "skipped", "reason": "Prompt 为空"}

        results["elapsed"] = time.time() - start
        return results


# ============================================================
# 模块级便捷函数
# ============================================================

_insight_generator: Optional[AIInsightGenerator] = None


def get_insight_generator() -> AIInsightGenerator:
    """获取全局 AI 洞察生成器实例"""
    global _insight_generator
    if _insight_generator is None:
        _insight_generator = AIInsightGenerator()
    return _insight_generator
