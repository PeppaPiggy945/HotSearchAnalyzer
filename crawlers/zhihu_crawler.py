"""
热搜爬虫
"""

from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem


class ZhihuCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('zhihu')


    def _get_api_url(self):
        """获取API"""

        return 'https://www.zhihu.com/api/v4/search/top_search/tabs/hot/items'

    def fetch(self) -> HotSearchResult | None:
        """获取热搜"""

        self.logger.info(f"正在爬取{self.platform_name}热门...")

        try:
            # 热门API
            url = self._get_api_url()
            response = self._make_request(url)
            data = response.json()
            items = self._parse(data)

            return self._create_result(items)

        except Exception as e:
            self.logger.error(f"{self.platform_name}热门爬取失败:{e}")


    def _parse(self, data: dict) -> List[HotSearchItem]:
        """解析API数据"""
        items = []
        if 'data' in data:
            for i, item in enumerate(data['data'], 1):
                try:
                    title = item.get('query_display', '')
                    items.append(HotSearchItem(
                        rank=i,
                        title=title,
                        url=f"https://www.zhihu.com/search?q={title}&type=content",
                    ))
                except Exception as e:
                    self.logger.debug(f"解析{self.platform_name}热门项失败: {e}")
                    continue

        return items



