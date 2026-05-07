"""
热搜爬虫
"""


from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem
from datetime import datetime


class WallCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('wallstreetcn')


    def _get_api_url(self):
        """获取API"""

        return 'https://api-one-wscn.awtmt.com/apiv1/content/articles/hot?period=all'

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


    def _parse(self, data: dict, use_weekly: bool = False) -> List[HotSearchItem]:
        """解析API数据"""
        try:
            # 选择日榜或周榜数据
            if use_weekly:
                items_key = "week_items"
                label = "周榜"
            else:
                items_key = "day_items"
                label = "日榜"

            # 获取文章列表
            articles = data.get("data", {}).get(items_key, [])

            # 提取热点信息
            hot_news = []
            for idx, article in enumerate(articles, 1):
                # 转换时间戳为可读格式
                display_time = article.get("display_time")
                if display_time:
                    time_str = datetime.fromtimestamp(display_time).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    time_str = "未知时间"

                # 创建额外信息字典
                extra_info = {
                    "hot_value": article.get("pageviews"),
                    "label": label,
                    "display_time": time_str,

                }

                # 创建热点项
                hot_item = HotSearchItem(
                    rank=idx,
                    title=article.get("title", ""),
                    url=article.get("uri"),
                )

                hot_news.append(hot_item)

            return hot_news

        except KeyError as e:
            self.logger.error(f"数据格式错误，缺少必要字段: {e}")
            return []
        except Exception as e:
            self.logger.error(f"未知错误: {e}")
            return []



