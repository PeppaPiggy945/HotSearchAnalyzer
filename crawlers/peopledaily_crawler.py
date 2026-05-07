"""
热搜爬虫
"""


from typing import List, Dict, Any, Optional
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem
import re


class PeopleDailyCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('people')

    def _get_api_url(self):
        """获取API"""
        response = self._make_request('https://www.people.com.cn')
        response.encoding = 'utf-8'
        text = response.text
        pattern = r'function rmhotlist\(\)\s*\{.*?url\s*:\s*"([^"]+)"'
        match = re.search(pattern, text, re.DOTALL)
        url = 'https://www.people.com.cn'
        if match:
            url = url + match.group(1)
        return url

    def fetch(self) -> HotSearchResult | None:
        """获取热搜"""
        self.logger.info(f"正在爬取{self.platform_name}热门...")

        try:
            url = self._get_api_url()
            response = self._make_request(url)
            response.encoding = 'utf-8'
            data = response.json()
            items = self._parse(data)

            return self._create_result(items)

        except Exception as e:
            self.logger.error(f"{self.platform_name}热门爬取失败:{e}")


    def _parse(self, data: dict) -> List[HotSearchItem]:
        """解析API数据"""
        # 1. 获取所有的数据组键（如 'data1', 'data2', ...）
        data_keys: List[str] = [key for key in data.keys() if key.startswith('data')]

        if not data_keys:
            raise ValueError("JSON数据中未找到任何以 'data' 开头的数据组。")

        # 2. 对键进行排序，并获取最后一个（即最新的一组数据）
        data_keys.sort()
        last_data_key: str = data_keys[-1]

        # 3. 提取目标数据列表
        target_data_list: List[Dict[str, Any]] = data.get(last_data_key, [])

        if not isinstance(target_data_list, list):
            raise TypeError(f"数据组 '{last_data_key}' 的值不是一个列表。")

        # 4. 遍历列表，创建HotSearchItem对象
        items: List[HotSearchItem] = []
        for idx, item in enumerate(target_data_list, start=1):
            if not isinstance(item, dict):
                continue  # 或记录日志，跳过无效条目
            title: str = item.get('title', '').strip()
            url: Optional[str] = item.get('url')
            # 如果URL为空字符串，也转为None
            if url is not None and len(url.strip()) == 0:
                url = None

            # 根据文档内容，未提供热度值、标签等信息，因此保持为None
            item = HotSearchItem(
                rank=idx,  # 使用列表顺序作为排名
                title=title,
                url=url,
            )
            items.append(item)

        return items



