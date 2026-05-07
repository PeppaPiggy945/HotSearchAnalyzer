"""
热搜爬虫
"""


from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem


class SinaCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('sina')


    def _get_api_url(self):
        """获取API"""

        return 'https://www.sina.com.cn/api/hotword.json'

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
        """
    从新浪热搜格式的JSON数据中提取热点信息列表。

    参数:
        json_data (dict): 符合示例格式的字典数据。

    返回:
        List[HotSearchItem]: 结构化后的热搜条目列表。
    """
        hot_search_list = []
        # 从JSON数据中获取数据列表，路径为：result -> data
        data_list = data.get("result", {}).get("data", [])

        for index, item in enumerate(data_list, start=1):  # start=1 使排名从1开始
            hot_item = HotSearchItem(
                rank=index,  # 使用枚举序号作为排名
                title=item.get("title"),  # 提取标题
                url=item.get("url"),  # 提取链接
            )
            hot_search_list.append(hot_item)

        return hot_search_list



