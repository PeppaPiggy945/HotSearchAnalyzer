"""
腾讯新闻爬虫
数据来源：tophub.today（第三方聚合平台）
"""

from typing import List
from datetime import datetime
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem


class TencentNewsCrawler(BaseCrawler):
    """腾讯新闻爬虫（通过 tophub.today 获取）"""

    API_URL = "https://tophub.today/node-items-by-date"
    NODE_ID = "27501"  # 腾讯新闻的 nodeid

    def __init__(self):
        super().__init__('tencentnews')

    def _get_api_url(self) -> str:
        return self.API_URL

    def fetch(self) -> HotSearchResult | None:
        """获取腾讯新闻"""
        self.logger.info(f"正在爬取{self.platform_name}...")

        try:
            url = self._get_api_url()
            data = {
                'p': '1',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'nodeid': self.NODE_ID,
            }
            response = self._make_request(url, method="POST", data=data)
            items = self._parse(response.json())
            return self._create_result(items)

        except Exception as e:
            self.logger.error(f"{self.platform_name}爬取失败: {e}")

    def _parse(self, data: dict) -> List[HotSearchItem]:
        """解析 tophub.today 返回的 JSON 数据"""
        items = []

        if not data or data.get('error'):
            self.logger.warning(f"API 返回错误: {data}")
            return items

        raw_items = data.get('data', {}).get('items', [])
        for i, item in enumerate(raw_items):
            try:
                title = item.get('title', '').strip()
                url = item.get('url', '').strip()

                if not title:
                    continue

                hot_item = HotSearchItem(
                    rank=i + 1,
                    title=title,
                    url=url if url else None
                )
                items.append(hot_item)

            except Exception as e:
                self.logger.debug(f"解析腾讯新闻条目失败: {e}")
                continue

        return items
