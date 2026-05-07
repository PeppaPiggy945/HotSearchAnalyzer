"""
热搜爬虫
"""

from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem
from bs4 import BeautifulSoup


class BaiduCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('baidu')


    def _get_api_url(self):
        """获取API"""

        return 'https://top.baidu.com/board?tab=realtime'

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
        """解析HTML数据，提取百度热搜内容"""

        soup = BeautifulSoup(html_content, 'html.parser')
        items = []

        # 找到所有热搜条目
        hot_items = soup.find_all('div', class_='category-wrap_iQLoo horizontal_1eKyQ')
        for hot_item in hot_items:
            try:
                # 提取排名
                index_div = hot_item.find('div', class_='index_1Ew5p')
                if not index_div:
                    continue

                # 获取排名文本（如"1", "2"等）
                rank_text = index_div.get_text(strip=True)
                if not rank_text or not rank_text.isdigit():
                    # 第一个条目可能没有数字排名，默认为0
                    if len(items) == 0:
                        rank = 0
                    else:
                        continue
                else:
                    rank = int(rank_text)

                # 提取标题和链接
                title_link = hot_item.find('a', class_='title_dIF3B')
                if not title_link:
                    continue

                title_div = title_link.find('div', class_='c-single-text-ellipsis')
                if not title_div:
                    continue

                title = title_div.get_text(strip=True)
                url = title_link.get('href', '').strip()

                if not title:
                    continue

                # 创建热点条目
                item = HotSearchItem(
                    rank=rank + 1,
                    title=title,
                    url=url
                )
                items.append(item)

            except Exception as e:
                self.logger.debug(f"解析新闻条目失败: {e}")
                continue

        return items




