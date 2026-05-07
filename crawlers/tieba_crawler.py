"""
百度贴吧话题热议榜单爬虫
"""

from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem
from bs4 import BeautifulSoup


class TiebaCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('tieba')

    def _get_api_url(self):
        """获取API"""
        return 'https://tieba.baidu.com/hottopic/browse/topicList?res_type=1'

    def fetch(self) -> HotSearchResult | None:
        """获取贴吧话题热议榜单"""

        self.logger.info(f"正在爬取{self.platform_name}话题热议榜单...")

        try:
            url = self._get_api_url()
            response = self._make_request(url)
            html_content = response.text
            items = self._parse(html_content)

            return self._create_result(items)

        except Exception as e:
            self.logger.error(f"{self.platform_name}话题热议榜单爬取失败:{e}")

    def _parse(self, html_content: str) -> List[HotSearchItem]:
        """解析HTML数据，提取贴吧话题热议榜单内容"""

        soup = BeautifulSoup(html_content, 'html.parser')
        items = []

        # 找到所有话题条目
        topic_items = soup.find_all('li', class_='topic-top-item')
        for topic_item in topic_items:
            try:
                # 提取排名
                rank = None
                icon_span = topic_item.find('span', class_='icon-top-0')
                if icon_span:
                    rank = 1
                else:
                    icon_span = topic_item.find('span', class_='icon-top-1')
                    if icon_span:
                        rank = 2
                    else:
                        icon_span = topic_item.find('span', class_='icon-top-2')
                        if icon_span:
                            rank = 3
                        else:
                            icon_span = topic_item.find('span', class_='icon-top-n')
                            if icon_span:
                                rank_text = icon_span.get_text(strip=True)
                                if rank_text.isdigit():
                                    rank = int(rank_text)

                if rank is None:
                    continue

                # 提取标题和链接
                title_link = topic_item.find('a', class_='topic-text')
                if not title_link:
                    continue

                title = title_link.get_text(strip=True)
                url = title_link.get('href', '').strip()

                if not title:
                    continue

                # 拼接完整URL
                if url.startswith('/'):
                    url = 'https://tieba.baidu.com' + url

                item = HotSearchItem(
                    rank=rank,
                    title=title,
                    url=url
                )
                items.append(item)

            except Exception as e:
                self.logger.debug(f"解析话题条目失败: {e}")
                continue

        return items
