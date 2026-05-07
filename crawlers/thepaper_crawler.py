"""
热搜爬虫
"""


from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem


class PaperCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('thepaper')


    def _get_api_url(self):
        """获取API"""

        return 'https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar'

    def fetch(self) -> HotSearchResult | None:
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
        hot_search_list = []
        hotnews = data.get("data", {}).get("hotNews", [])
        for index, item in enumerate(hotnews, start=1):  # start=1 使排名从1开始
            hot_item = HotSearchItem(
                rank=index,  # 使用枚举序号作为排名
                title=item.get("name"),  # 提取标题
                url=f"https://www.thepaper.cn/newsDetail_forward_{item.get('contId')}",  # 提取链接
            )
            hot_search_list.append(hot_item)

        return hot_search_list


