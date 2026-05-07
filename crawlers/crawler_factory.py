"""
爬虫工厂
支持动态导入爬虫模块
"""

import importlib
from typing import Type, Dict
from core.config_manager import ConfigManager
from core.logger import get_logger


class HotSearchCrawlerFactory:
    """热搜爬虫工厂 - 支持动态导入配置"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.config_manager = ConfigManager()
        self._crawlers = {}  # platform_key -> crawler_class or (module, class_name) tuple
        self._key_to_name = {}  # platform_key -> platform_name
        self._register_crawlers_from_config()
        self.logger.info(f"爬虫工厂初始化完成，已注册 {len(self._crawlers)} 个爬虫")

    def _register_crawlers_from_config(self):
        """从配置文件注册爬虫（仅保存路径，不立即导入）"""
        platforms = self.config_manager.platform_configs

        for platform_key, config in platforms.items():
            if config.get('enabled', True):
                crawler_module = config.get('crawler_module')
                crawler_class = config.get('crawler_class')

                if crawler_module and crawler_class:
                    platform_name = config.get('name', platform_key)
                    # 延迟导入：只存储模块路径和类名
                    self._crawlers[platform_key] = (crawler_module, crawler_class)
                    self._key_to_name[platform_key] = platform_name
                    self.logger.debug(f"注册爬虫: {platform_name} ({crawler_module}.{crawler_class})")

    def _get_crawler_class(self, platform: str):
        """获取爬虫类（按需导入）"""
        entry = self._crawlers.get(platform)
        if entry is None:
            return None
        if isinstance(entry, tuple):
            module_name, class_name = entry
            try:
                module = importlib.import_module(module_name)
                crawler = getattr(module, class_name)
                # 缓存导入结果，后续直接使用
                self._crawlers[platform] = crawler
                return crawler
            except (ImportError, AttributeError) as e:
                self.logger.error(f"无法加载爬虫模块 {module_name}.{class_name}: {e}")
                return None
        return entry

    def create_crawler(self, platform: str):
        """创建爬虫实例（同时支持 platform_key 和 platform_name）"""
        # 先尝试 platform_key
        crawler_class = self._get_crawler_class(platform)
        if not crawler_class:
            # 回退到 platform_name 查找
            for key, name in self._key_to_name.items():
                if name == platform:
                    crawler_class = self._get_crawler_class(key)
                    break
        if not crawler_class:
            raise ValueError(f"不支持的平台: {platform}")
        return crawler_class()

    def get_available_platforms(self):
        """获取支持的平台 key 列表"""
        return list(self._crawlers.keys())

    def get_available_platform_names(self):
        """获取支持的平台中文名称列表"""
        return list(self._key_to_name.values())

    def register_crawler(self, platform_key: str, crawler_class):
        """注册新的爬虫"""
        self._crawlers[platform_key] = crawler_class

    def unregister_crawler(self, platform_key: str):
        """注销爬虫"""
        if platform_key in self._crawlers:
            del self._crawlers[platform_key]
            self._key_to_name.pop(platform_key, None)

    def reload_crawlers(self):
        """重新加载爬虫配置（热更新）"""
        self.config_manager.reload_configs()
        self._crawlers.clear()
        self._key_to_name.clear()
        self._register_crawlers_from_config()