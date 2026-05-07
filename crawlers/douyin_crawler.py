"""
热搜爬虫
"""

from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem


class DouyinCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('douyin')


    def _get_api_url(self):
        """获取API"""

        url = 'https://www.douyin.com/aweme/v1/web/hot/search/list/'
        return url

    def fetch(self) -> HotSearchResult | None:

        self.logger.info(f"正在爬取{self.platform_name}热门...")
        try:
            url = self._get_api_url()
            response = self._make_request(url)
            data = response.json()
            items = self._parse(data)
            return self._create_result(items)

        except Exception as e:
            self.logger.error(f"{self.platform_name}热门爬取失败:{e}")


    def _parse(self, data: dict) -> List[HotSearchItem]:
        """解析API数据"""
        hot_items = []

        # 获取主热搜列表
        word_list = data.get("data", {}).get("word_list", [])

        for item in word_list:
            # 基础信息
            rank = item.get("position", 0)
            title = item.get("word", "")

            if not title or rank == 0:
                continue

            # 标签处理
            label = None
            label_value = item.get("label")
            if label_value is not None:
                # 如果有标签URL，可以添加更多标签信息
                label_url = item.get("label_url")
                if label_url:
                    # 根据文档，label是整数，但我们需要字符串
                    # 这里我们可以将label数值转换为更有意义的描述
                    label_mapping = {
                        0: "普通",
                        1: "新",  # 基于文档中的示例
                        3: "热",  # 基于文档中的示例
                        8: "影综",
                        9: "音乐",
                        11: "影视",
                        13: "娱乐",
                        16: "辟谣"
                    }
                    label_desc = label_mapping.get(label_value, f"标签{label_value}")
                    label = f"{label_desc}"
                else:
                    label = str(label_value)

            # URL处理 - 使用group_id构造可能的详情页URL
            url = None
            group_id = item.get("group_id")
            if group_id:
                url = f"https://www.douyin.com/search/{title}"

            # 额外信息
            extra = {
                "label": label,
                "hot_value": item.get("hot_value"),
                "event_time": item.get("event_time"),
                "is_new": item.get("is_n1", False),
            }

            # 清理None值
            extra = {k: v for k, v in extra.items() if v is not None}

            hot_item = HotSearchItem(
                rank=rank,
                title=title,
                url=url,
            )

            hot_items.append(hot_item)

        # 按排名排序
        hot_items.sort(key=lambda x: x.rank)
        return hot_items


