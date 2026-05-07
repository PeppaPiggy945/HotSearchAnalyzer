"""
B站热门爬虫
"""

import time
from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem
import math
import hashlib

class BilibiliCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('bilibili')


    def _get_api_url(self):
        """获取B站API"""
        def jm(wts, web_location="333.1007"):
            ne = "ea1db124af3c7062474693fa704f4ff8"
            p = 'limit=10&platform=web&web_location=' + web_location + '&wts=' + wts + ne
            md5_hash = hashlib.md5(p.encode('utf-8'))
            return md5_hash.hexdigest()

        wts = str(math.floor(time.time()))
        web_location = "333.1007"
        w_rid = jm(wts, web_location)
        api_url = f"https://api.bilibili.com/x/web-interface/wbi/search/square?limit=10&platform=web&web_location={web_location}&w_rid={w_rid}&wts={wts}"
        return api_url

    def fetch(self) -> HotSearchResult | None:
        """获取B站热门"""
        self.logger.info(f"正在爬取{self.platform_name}热门...")

        try:
            # B站热门API
            url = self._get_api_url()
            response = self._make_request(url)
            data = response.json()
            items = self._parse(data)

            if not items:
                items = None

            return self._create_result(items)

        except Exception as e:
            self.logger.error(f"{self.platform_name}热门爬取失败: {e}")

    def _parse(self, data: dict) -> List[HotSearchItem]:
        """解析API数据"""
        items = []
        if data.get('code') == 0 and 'data' in data and 'trending' in data['data'] and 'list' in data['data']['trending']:
            for i, item in enumerate(data['data']['trending']['list'], 1):
                try:
                    title = item.get('show_name', '')
                    hot_value = item.get('heat_score', 0)  # 用播放量作为热度参考
                    items.append(HotSearchItem(
                        rank=i,
                        title=title,
                        url=f"https://search.bilibili.com/all?keyword={title}",
                    ))
                except Exception as e:
                    self.logger.debug(f"解析{self.platform_name}热门项失败: {e}")
                    continue

        return items

