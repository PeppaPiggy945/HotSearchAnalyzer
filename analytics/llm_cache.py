# analytics/llm_cache.py
"""
LLM 推理结果缓存 — 统一管理 llm_middleware 和 llm_classifier 的缓存。

过期淘汰 + 数量上限 LRU，缓存文件为 JSON 格式，按 cache_type 区分不同用途。
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Optional

from core.logger import get_logger

logger = get_logger(__name__)


class LLMCache:
    """LLM 推理结果缓存，支持过期淘汰和数量上限。"""

    def __init__(
        self,
        cache_type: str,
        result_key: str = "r",
        cache_dir: Optional[Path] = None,
        expire_days: int = 7,
        max_entries: int = 5000,
    ):
        """
        Args:
            cache_type: 缓存类型标识，如 "classify"、"validate"、"title"
            result_key: 缓存值在字典中的键名（classify 用 "c"，middleware 用 "r"）
            cache_dir: 缓存目录（默认从配置读取）
            expire_days: 过期天数
            max_entries: 最大条目数
        """
        self._cache: Dict[str, dict] = {}
        self._cache_file: Optional[Path] = None
        self._expire_days = expire_days
        self._max_entries = max_entries
        self._result_key = result_key
        self._init_cache(cache_type, cache_dir)

    @staticmethod
    def make_key(*texts: str) -> str:
        """生成稳定的 MD5 缓存键"""
        normalized = "|".join(t.strip() for t in texts if t.strip())
        if not normalized:
            normalized = ""
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def _init_cache(self, cache_type: str, cache_dir: Optional[Path]):
        if cache_dir is None:
            try:
                from config.settings import get_settings
                cache_dir = get_settings().paths.LLM_CACHE_DIR
            except Exception:
                cache_dir = Path(__file__).parent.parent / ".llm_cache"

        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = cache_dir / f"{cache_type}_cache.json"

        # 读取缓存清理配置
        try:
            from core.config_manager import ConfigManager
            cache_cfg = ConfigManager().analytics_config.get("llm", {}).get("cache", {})
            self._expire_days = int(cache_cfg.get("expire_days", self._expire_days))
            self._max_entries = int(cache_cfg.get("max_entries", self._max_entries))
        except Exception:
            pass

        if self._cache_file.is_file():
            try:
                raw = json.loads(self._cache_file.read_text("utf-8"))
                self._cache = {
                    k: v if isinstance(v, dict) else {self._result_key: v, "t": 0}
                    for k, v in raw.items()
                }
            except Exception:
                self._cache = {}

        if self._cache:
            self._cleanup()

    def _cleanup(self):
        """过期淘汰 + 数量上限淘汰"""
        now = time.time()
        expire_sec = self._expire_days * 86400
        expired = [
            k for k, v in self._cache.items()
            if v["t"] > 0 and (now - v["t"]) > expire_sec
        ]
        for k in expired:
            del self._cache[k]
        if len(self._cache) > self._max_entries:
            sorted_keys = sorted(self._cache, key=lambda k: self._cache[k]["t"])
            over = len(self._cache) - self._max_entries
            for k in sorted_keys[:over]:
                del self._cache[k]

    def get(self, key: str) -> Optional[str]:
        """根据缓存键查询结果，命中则刷新访问时间"""
        entry = self._cache.get(key)
        if entry is None:
            return None
        entry["t"] = time.time()
        return entry.get(self._result_key)

    def put(self, key: str, result: str):
        """写入缓存（已有键不覆盖）"""
        if key not in self._cache:
            self._cache[key] = {self._result_key: result, "t": time.time()}

    def save(self):
        """持久化到磁盘"""
        if not self._cache_file:
            return
        try:
            self._cleanup()
            self._cache_file.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2), "utf-8"
            )
        except Exception as e:
            logger.warning(f"缓存写入失败: {e}")

    def stats(self) -> dict:
        return {
            "size": len(self._cache),
            "file": str(self._cache_file) if self._cache_file else None,
        }
