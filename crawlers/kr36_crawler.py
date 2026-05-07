"""
热搜爬虫
"""

from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem
from bs4 import BeautifulSoup


class Kr36Crawler(BaseCrawler):
    def __init__(self):
        super().__init__('kr36')


    def _get_api_url(self):
        """获取API"""

        return 'https://www.36kr.com/newsflashes/catalog/1'

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
        """解析API数据"""
        """
            从36氪快讯HTML中提取热点信息

            参数:
                html_content: 网页HTML内容字符串

            返回:
                List[HotSearchItem]: 热点新闻项列表
            """
        soup = BeautifulSoup(html_content, 'html.parser')
        hot_news_items = []

        # 查找所有快讯项
        news_items = soup.find_all('div', class_='newsflash-item')

        for idx, item in enumerate(news_items, 1):
            try:
                # 提取标题
                title_elem = item.find('a', class_='item-title')
                title = title_elem.text.strip() if title_elem else ""

                # 提取链接
                url = 'https://www.36kr.com' + title_elem.get('href') if title_elem else None

                # 提取时间信息
                time_elem = item.find('span', class_='time')
                time_text = time_elem.text.strip() if time_elem else ""

                # 提取描述内容
                desc_elem = item.find('div', class_='item-desc')
                if desc_elem:
                    desc_span = desc_elem.find('span')
                    description = desc_span.text.strip() if desc_span else ""

                    # 提取原文链接
                    link_elem = desc_elem.find('a', class_='link')
                    source_link = link_elem.get('href') if link_elem else None
                else:
                    description = ""
                    source_link = None

                # 构建额外信息字典
                extra_info = {
                    'time': time_text,
                    'description': description,
                    'source_link': source_link
                }

                # 创建HotSearchItem对象
                hot_item = HotSearchItem(
                    rank=idx,
                    title=title,
                    url=url,
                )

                hot_news_items.append(hot_item)

            except Exception as e:
                self.logger.debug(f"解析过程中发生错误: {e}")
                return []

        return hot_news_items


