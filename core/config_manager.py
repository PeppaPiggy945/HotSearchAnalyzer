# core/config_manager.py
"""
统一配置管理器
负责加载和合并所有配置，提供简洁的获取接口
"""
import yaml
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from config.settings import get_settings
from core.logger import get_logger


class ConfigManager:
    """
    统一的配置管理器
    负责加载和合并：settings.py + 所有YAML配置
    设计原则：只提供获取配置的接口，不提供复杂的增删改查
    """

    _instance = None

    def __new__(cls, config_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_configs(config_path=config_path)
        return cls._instance

    def _init_configs(self, config_path: str = None):
        """初始化加载所有配置"""
        self.logger = get_logger(__name__)
        self.settings = get_settings()
        self.paths = self.settings.paths
        self._custom_config_path = config_path

        # 确保配置目录存在
        self.paths.create_dirs()

        # 加载所有配置文件
        self._load_all_configs()
        self.logger.info("配置管理器初始化完成")

    def _load_all_configs(self):
        """加载所有配置文件"""
        # 1. 平台配置
        self.platform_configs = self._load_yaml_config(
            "platform_configs.yaml",
            default={"platforms": {}}
        ).get("platforms", {})

        # 2. 头部配置
        self.headers_config = self._load_yaml_config(
            "headers_config.yaml",
            default={
                "platform_headers": {},
                "common_headers": {},
            }
        )

        # 3. 分析配置
        self.analytics_config = self._load_yaml_config(
            "analytics_config.yaml",
            default={}
        )

        # 4. 事件关键词配置
        self.event_keywords_config = self._load_yaml_config(
            "event_keywords.yaml",
            default={"event_keywords": {}}
        )

        # 5. 停用词配置
        self.stop_words_config = self._load_yaml_config(
            "stop_words.yaml",
            default={"stop_words": []}
        )

        # 6. 用户配置
        user_config_file = self._custom_config_path or "user_config.yaml"
        self.user_config = self._load_yaml_config(
            user_config_file,
            default={"user_config": {
            'crawler': {
                'mode': 'manual',
                'platforms': {
                    'enabled': [],
                    'disabled': [],
                    'max_items_per_platform': 10,
                },
                'schedule': {
                    'time': '08:00',
                    'interval_minutes': 60,
                },
                'retention': {
                    'max_files_per_platform': 80,
                    'keep_days': 30,
                },
            },
            'analysis': {
                'report': {
                    'format': 'markdown',
                    'save_to_file': True,
                    'output_dir': 'outputs/analysis',
                },
            },
            'prompt': {
                'auto_generate': True,
                'output_dir': 'outputs/prompts',
                'template': 'templates/analysis_prompt.md',
            },
            'logging': {
                'level': 'INFO',
                'console': True,
                'file': True,
            },
            'service': {
                'port': 5000,
                'refresh_interval': 300,
                'allow_cors': True,
            },
        }}
        )


    def _load_yaml_config(self, filename: str, default: Any = None) -> Dict[str, Any]:
        """加载YAML配置文件"""
        config_path = self.paths.CONFIG_DIR / filename

        if not config_path.exists():
            if default is not None:
                self.logger.warning(f"配置文件不存在，使用默认值: {config_path}")
                return default
            else:
                raise FileNotFoundError(f"配置文件不存在: {config_path}")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                self.logger.debug(f"成功加载配置文件: {config_path}")
                return config
        except Exception as e:
            self.logger.error(f"加载配置文件失败 {config_path}: {e}")
            return default or {}

    def reload_configs(self):
        """重新加载所有配置（热更新）"""
        self._load_all_configs()
        return True

    # ==================== 用户配置相关 ====================

    def get_user_config(self) -> Dict[str, Any]:
        return self.user_config

    # ==================== 平台配置相关 ====================

    def get_platform_config(self, platform_key: str) -> Dict[str, Any]:
        """获取单个平台的完整配置（合并 settings.py + user_config.yaml，user_config 优先级最高）"""
        if platform_key not in self.platform_configs:
            raise ValueError(f"平台配置不存在: {platform_key}")

        platform_config = self.platform_configs[platform_key].copy()

        # 获取分类
        category = platform_config.get("category", "other")
        sub_category = platform_config.get("sub_category", "")

        # user_config 中的爬取平台配置
        crawler_plat_cfg = self.user_config.get("crawler", {}).get("platforms", {})
        user_enabled_list = crawler_plat_cfg.get("enabled", [])
        user_disabled_list = crawler_plat_cfg.get("disabled", [])
        user_max_items = crawler_plat_cfg.get("max_items_per_platform", None)

        # 合并通用配置
        merged_config = {
            # 平台特定配置（platform_configs.yaml 为基准）
            "key": platform_key,
            "name": platform_config.get("name", platform_key),
            "category": category,
            "sub_category": sub_category,
            "enabled": platform_config.get("enabled", True),
            "base_url": platform_config.get("base_url", ""),
            "max_fetch_items": platform_config.get("max_fetch_items"),
            "default_fetch_items": platform_config.get("default_fetch_items", 10),

            # 从settings.py继承的全局配置
            "timeout": self.settings.request.TIMEOUT,
            "max_retries": self.settings.request.MAX_RETRIES,
            "connect_timeout": self.settings.request.CONNECT_TIMEOUT,
            "read_timeout": self.settings.request.READ_TIMEOUT,
            "request_delay": self.settings.request.REQUEST_DELAY,
            "max_concurrent_requests": self.settings.request.MAX_CONCURRENT_REQUESTS,

            # 分类显示信息
            "category_display_name": self.settings.platform.get_category_display_name(category),
            "category_color": self.settings.platform.get_category_color(category),

            # 数据配置
            "data_format": self.settings.data.DEFAULT_FORMAT,
            "enable_cache": self.settings.data.ENABLE_CACHE,
        }

        # 应用 user_config 的 enabled/disabled 列表（user_config 优先级最高）
        if platform_key in user_disabled_list:
            merged_config["enabled"] = False
        elif user_enabled_list and platform_key not in user_enabled_list:
            merged_config["enabled"] = False

        # 应用 user_config 的全局 max_items 限制
        if user_max_items is not None and merged_config["max_fetch_items"] is not None:
            merged_config["max_fetch_items"] = min(merged_config["max_fetch_items"], user_max_items)
        elif user_max_items is not None:
            merged_config["max_fetch_items"] = user_max_items

        return merged_config

    def get_platforms_by_category(self, category: str) -> List[str]:
        """获取指定分类的所有平台"""
        return [
            key for key, config in self.platform_configs.items()
            if config.get("category") == category and config.get("enabled", True)
        ]

    def get_all_enabled_platforms(self) -> List[str]:
        """获取所有启用的平台（考虑 user_config 的 enabled/disabled 列表）"""
        crawler_plat_cfg = self.user_config.get("crawler", {}).get("platforms", {})
        user_enabled_list = crawler_plat_cfg.get("enabled", [])
        user_disabled_list = crawler_plat_cfg.get("disabled", [])

        result = []
        for key, config in self.platform_configs.items():
            if not config.get("enabled", True):
                continue
            if key in user_disabled_list:
                continue
            if user_enabled_list and key not in user_enabled_list:
                continue
            result.append(key)
        return result

    def get_platform_quota(self, platform_key: str, requested_count: int) -> int:
        """获取平台的配额（限制请求条数）"""
        config = self.get_platform_config(platform_key)
        max_items = config.get("max_fetch_items", 20)
        return min(requested_count, max_items)

    # ==================== 头部配置相关 ====================

    def get_merged_headers(self, platform_key: str,
                           dynamic_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        获取合并后的请求头
        合并顺序: 默认头部 -> 通用头部 -> 平台头部 -> 动态头部
        """
        # 1. 从settings.py获取默认头部
        headers = self.settings.request.DEFAULT_HEADERS.copy()

        # 2. 添加通用头部
        common_headers = self.headers_config.get("common_headers", {})
        headers.update(common_headers)

        # 3. 添加平台特定头部
        platform_headers = self.headers_config.get("platform_headers", {}).get(platform_key, {})
        headers.update(platform_headers)

        # 4. 添加动态头部（优先级最高）
        if dynamic_headers:
            headers.update(dynamic_headers)

        return headers

    def get_platform_headers(self, platform_key: str) -> Dict[str, str]:
        """获取平台的原始头部配置（不合并）"""
        return self.headers_config.get("platform_headers", {}).get(platform_key, {}).copy()

    # ==================== 分析配置相关 ====================

    def get_event_keywords(self) -> Dict[str, List[str]]:
        """
        获取所有事件类型的关键词

        Returns:
            事件类型字符串到关键词列表的映射
            例如: {"politics": ["政治", "政府", ...], "economy": ["经济", ...]}
        """
        raw = self.event_keywords_config.get("event_keywords", {})
        result = {}
        for k, v in raw.items():
            if isinstance(v, dict):
                result[str(k)] = [str(kw) for kw in v.get("keywords", [])]
            elif isinstance(v, list):
                result[str(k)] = [str(kw) for kw in v]
        return result

    def get_event_keywords_by_type(self, event_type: str) -> List[str]:
        """
        获取指定事件类型的关键词

        Args:
            event_type: 事件类型字符串，如 "politics", "economy" 等

        Returns:
            关键词列表
        """
        event_keywords = self.get_event_keywords()
        return event_keywords.get(event_type, [])

    def get_stop_words(self) -> set:
        """
        获取所有停用词

        Returns:
            停用词集合
        """
        return set(str(kw) for kw in self.stop_words_config.get("stop_words", []))

    def get_type_weight_coefficients(self) -> Dict[str, float]:
        """
        获取事件类型权重系数

        Returns:
            事件类型字符串到权重系数的映射
        """
        return self.event_keywords_config.get("type_weight_coefficients", {})

    def get_politics_strong_exclusion(self) -> set:
        """
        获取政治类强排除词

        Returns:
            强排除词集合（出现时政治类得分清零）
        """
        raw = self.event_keywords_config.get("politics_strong_exclusion", [])
        return set(str(kw) for kw in raw)

    def get_politics_soft_exclusion(self) -> set:
        """
        获取政治类软排除词

        Returns:
            软排除词集合（出现时政治类得分降低50%）
        """
        raw = self.event_keywords_config.get("politics_soft_exclusion", [])
        return set(str(kw) for kw in raw)

    def get_fallback_priority_keywords(self) -> Dict[str, List[str]]:
        """
        获取兜底分类优先级关键词

        Returns:
            事件类型字符串到关键词列表的映射
        """
        raw = self.event_keywords_config.get("fallback_priority_keywords", {})
        result = {}
        for k, v in raw.items():
            result[str(k)] = [str(kw) for kw in v]
        return result


    # ==================== 工具方法 ====================

    def is_platform_enabled(self, platform_key: str) -> bool:
        """检查平台是否启用（考虑 user_config 的 enabled/disabled 列表）"""
        if platform_key not in self.platform_configs:
            return False
        if not self.platform_configs[platform_key].get("enabled", True):
            return False
        # user_config 的 enabled/disabled 列表
        crawler_plat_cfg = self.user_config.get("crawler", {}).get("platforms", {})
        if platform_key in crawler_plat_cfg.get("disabled", []):
            return False
        user_enabled_list = crawler_plat_cfg.get("enabled", [])
        if user_enabled_list and platform_key not in user_enabled_list:
            return False
        return True

    def get_settings(self):
        """获取全局settings对象"""
        return self.settings