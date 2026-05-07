"""
热搜爬虫
"""

from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem
from bs4 import BeautifulSoup


class IthomeCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('ithome')


    def _get_api_url(self):
        """获取API"""

        return 'https://www.ithome.com/block/rank.html'

    def fetch(self) -> HotSearchResult | None:
        """获取热点"""

        self.logger.info(f"正在爬取{self.platform_name}热门...")

        try:
            # 热门API
            url = self._get_api_url()
            response = self._make_request(url)
            data = response.text
            items = self._parse(data)

            return self._create_result(items)

        except Exception as e:
            self.logger.error(f"{self.platform_name}热门爬取失败:{e}")


    def _parse(self, html_content: str) -> List[HotSearchItem]:
        """解析HTML数据，提取日榜内容"""

        soup = BeautifulSoup(html_content, 'html.parser')
        items = []

        # 找到日榜的 ul 元素（id="d-1"）
        daily_list = soup.find('ul', {'id': 'd-1'})
        if not daily_list:
            self.logger.warning("未找到日榜数据")
            return items

        # 提取每条新闻
        li_list = daily_list.find_all('li')
        for rank, li in enumerate(li_list, start=1):
            try:
                # 提取标题和链接
                a_tag = li.find('a')
                if not a_tag:
                    continue

                title = a_tag.get('title', '').strip()
                url = a_tag.get('href', '').strip()

                if not title:
                    continue

                # 创建热点条目
                item = HotSearchItem(
                    rank=rank,
                    title=title,
                    url=url
                )
                items.append(item)

            except Exception as e:
                self.logger.debug(f"解析新闻条目失败: {e}")
                continue

        return items


