"""
热搜爬虫
"""

from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem



class HuxiuCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('huxiu')


    def _get_api_url(self):
        """获取API"""

        return 'https://api-article.huxiu.com/web/index/hotArticles'

    def fetch(self) -> HotSearchResult | None:
        """获取热搜"""

        self.logger.info(f"正在爬取{self.platform_name}热门...")

        try:
            # 热门API
            url = self._get_api_url()
            response = self._make_request(url=url, method='POST', data = {
                'platform': 'www',
                'time_type': '2',
                'pagesize': '6',
            })
            data = response.json()
            items = self._parse(data)

            return self._create_result(items)

        except Exception as e:
            self.logger.error(f"{self.platform_name}热门爬取失败:{e}")


    def _parse(self, data_dict: dict) -> List[HotSearchItem]:
        """解析API数据"""
        result = []

        try:

            # 获取data数组
            items_data = data_dict.get("data", [])

            # 遍历每个项目
            for index, item in enumerate(items_data, 1):
                # 构建extra字段，包含所有原始数据
                count_info = item.get("count_info", {})
                hot_value = count_info.get("favorite_num")
                extra_info = {
                    "hot_value": hot_value,
                    "aid": item.get("aid"),
                    "pic_path": item.get("pic_path"),
                    "is_original": item.get("is_original", False),
                    "user_info": item.get("user_info", {}),
                    "is_video_article": item.get("is_video_article", False),
                    "count_info": item.get("count_info", {})
                }


                # 创建HotSearchItem对象
                hot_item = HotSearchItem(
                    rank=index,  # 使用遍历索引作为排名
                    title=item.get("title", ""),
                    url=item.get("url"),
                )

                result.append(hot_item)

        except Exception as e:
            self.logger.debug(f"解析过程中发生错误: {e}")
            return []

        return result

