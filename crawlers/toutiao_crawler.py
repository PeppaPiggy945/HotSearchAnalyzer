"""
热搜爬虫
"""

from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem


class ToutiaoCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('toutiao')


    def _get_api_url(self):
        """获取API"""
        signature = ''
        return f'https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc&_signature={signature}'

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
        hot_items = []
        if 'data' in data:
            data_list = data.get("data", [])
            for index, item in enumerate(data_list, start=1):  # rank从1开始
                # 提取核心字段
                title = item.get("Title")

                # 处理热度值：尝试转换为整数，失败则设为None
                hot_value_str = item.get("HotValue")
                try:
                    hot_value = int(hot_value_str) if hot_value_str else None
                except (ValueError, TypeError):
                    hot_value = None

                # 处理URL：取`Url`字段，若无则尝试Schema字段
                url = item.get("Url") or item.get("Schema")

                # 处理标签
                label = item.get("Label")

                # 构建extra字段，包含其他可能有用的原始信息
                extra_info = {
                    'label': label,
                    'hot_value': hot_value,
                    "label_desc": item.get("LabelDesc"),
                    "image_url": (item.get("Image") or {}).get("url") if item.get("Image") else None
                }
                # 清理空值
                extra_info = {k: v for k, v in extra_info.items() if v is not None}

                # 创建HotSearchItem对象
                hot_item = HotSearchItem(
                    rank=index,
                    title=title,
                    url=url,
                )

                hot_items.append(hot_item)

        return hot_items


