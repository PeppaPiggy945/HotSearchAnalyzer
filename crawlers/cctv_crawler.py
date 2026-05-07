"""
热搜爬虫
"""

from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem
import json


class CCTVNewsCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('cctv')

    def _get_api_url(self):
        """获取API"""

        return 'https://news.cctv.com/2019/07/gaiban/cmsdatainterface/page/news_1.jsonp?cb=news'

    def fetch(self) -> HotSearchResult | None:
        """获取热搜"""

        self.logger.info(f"正在爬取{self.platform_name}热门...")

        try:
            # 热门API
            url = self._get_api_url()
            response = self._make_request(url)
            response.encoding = 'utf-8'
            data = response.text.replace('news(', '').replace(')', '')
            items = self._parse(json.loads(data))

            return self._create_result(items)

        except Exception as e:
            self.logger.error(f"{self.platform_name}热门爬取失败:{e}")


    def _parse(self, data: dict) -> List[HotSearchItem]:
        """
        从CCTV新闻JSON数据中提取热点信息

        参数:
            json_data: JSON格式的字符串数据

        返回:
            热点信息列表，按原始顺序排列
        """
        try:
            # 获取新闻列表
            news_list = data.get("data", {}).get("list", [])

            hotspot_items = []

            # 遍历新闻列表，按顺序提取信息
            for idx, news in enumerate(news_list, start=1):
                # 提取额外信息
                extra_info = {
                    "focus_date": news.get("focus_date", ""),
                    "brief": news.get("brief", ""),
                    "image": news.get("image", ""),
                    'keywords': news.get("keywords", ""),
                }


                # 创建HotSearchItem对象
                item = HotSearchItem(
                    rank=idx,
                    title=news.get("title", ""),
                    url=news.get("url", ""),
                )

                hotspot_items.append(item)

            return hotspot_items
        except Exception as e:
            self.logger.error(f"解析JSON数据时出错: {e}")
            return []


