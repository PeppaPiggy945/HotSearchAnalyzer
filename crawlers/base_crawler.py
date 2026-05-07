"""
爬虫基类
"""


import time
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
import requests
from fake_useragent import UserAgent
from core.models import HotSearchResult, HotSearchItem
from core.config_manager import ConfigManager
from core.logger import get_logger


class BaseCrawler(ABC):
    """热搜爬虫基类"""

    @staticmethod
    def _generate_user_agent() -> str:
        """生成一个随机的 User-Agent"""
        try:
            ua = UserAgent()
            return ua.random
        except Exception:
            # 如果 fake-useragent 失败，使用一个默认的 user-agent
            return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0'

    def __init__(self, platform_key: str):
        # 1. 初始化日志记录器
        self.logger = get_logger(__name__)

        # 2. 获取配置管理器
        self.config_manager = ConfigManager()

        # 3. 获取平台配置
        self.platform_config = self.config_manager.get_platform_config(platform_key)
        self.platform_key = platform_key
        self.platform_name = self.platform_config.get("name", platform_key)

        self.logger.info(f"初始化爬虫: {self.platform_name} ({platform_key})")

        # 4. 设置HTTP会话
        self.session = requests.Session()

        # 5. 设置合并后的请求头
        headers = self.config_manager.get_merged_headers(platform_key)

        # 如果没有 user-agent，则自动生成一个
        if not any(key.lower() == 'user-agent' for key in headers.keys()):
            headers['User-Agent'] = self._generate_user_agent()
            self.logger.debug("自动生成 User-Agent")

        self.session.headers.update(headers)

        # 6. 设置超时
        self.timeout = (
            self.platform_config.get("connect_timeout"),
            self.platform_config.get("read_timeout")
        )

        # 7. 获取其他配置
        self.max_retries = self.platform_config.get("max_retries", 3)
        self.request_delay = self.platform_config.get("request_delay", 1.0)

    def _create_result(self, items: List[HotSearchItem]) -> HotSearchResult:
        """创建标准化结果对象"""
        default = self.platform_config.get("default_fetch_items") or 10
        max_items = self.platform_config.get("max_fetch_items")
        limit = min(default, max_items) if max_items else default
        return HotSearchResult(
            platform_key=self.platform_key,
            platform_name=self.platform_name,
            category=self.platform_config.get("category"),
            sub_category=self.platform_config.get("sub_category"),
            fetch_time=datetime.now().strftime('%Y-%m-%d_%H_%M_%S'),
            requested_count=limit,
            actual_count=len(items[:limit]),
            max_support_count=len(items),
            items=items[:limit]
        )

    def _make_request(self, url: Optional[str] = None, method: str = "GET",
                     max_retries: int = None, backoff_factor: float = 0.5,
                     **kwargs) -> requests.Response | None:
        """
        发送HTTP请求，带指数退避重试机制

        Args:
            url: 请求URL
            method: HTTP方法
            max_retries: 最大重试次数（默认使用平台配置值）
            backoff_factor: 退避因子，等待时间 = backoff_factor * (2 ** attempt)
            **kwargs: 传递给 requests 的额外参数
        """
        url = url or self.platform_config.get("base_url")
        if not url:
            raise ValueError("没有指定URL")

        retries = max_retries if max_retries is not None else self.max_retries
        self.logger.debug(f"发起请求: {method} {url}")

        last_exception = None
        for attempt in range(retries):
            try:
                # 遵守请求间隔
                if hasattr(self, '_last_request_time'):
                    elapsed = time.time() - self._last_request_time
                    if elapsed < self.request_delay:
                        time.sleep(self.request_delay - elapsed)

                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=self.timeout,
                    **kwargs
                )
                response.raise_for_status()

                self._last_request_time = time.time()
                self.logger.debug(f"请求成功: {method} {url} (状态码: {response.status_code})")
                return response

            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt == retries - 1:
                    self.logger.error(f"请求失败（已达最大重试次数 {retries}）: {method} {url} - {e}")
                    raise

                wait_time = backoff_factor * (2 ** attempt)
                self.logger.warning(f"请求失败，{wait_time:.1f}秒后重试 (第{attempt + 1}/{retries}次): {method} {url} - {e}")
                time.sleep(wait_time)

    @abstractmethod
    def _get_api_url(self) -> str:
        pass

    @abstractmethod
    def fetch(self) -> HotSearchResult:
        pass

    @abstractmethod
    def _parse(self, data: dict) -> List[HotSearchItem]:
        pass

    def get_platform_info(self) -> dict:
        """获取平台信息"""
        return {
            "key": self.platform_key,
            "name": self.platform_name,
            "category": self.platform_config.get("category"),
            "max_items": self.platform_config.get("max_fetch_items"),
        }