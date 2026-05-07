"""
热搜爬虫
"""

from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem
from bs4 import BeautifulSoup


class CaixinCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('caixin')


    def _get_api_url(self):
        """获取API"""

        return 'https://economy.caixin.com/'

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
        """解析HTML数据，提取要闻内容"""

        soup = BeautifulSoup(html_content, 'html.parser')
        items = []

        # 找到要闻部分的容器
        yaowen_section = soup.find('div', class_='yaowen')
        if not yaowen_section:
            self.logger.warning("未找到要闻部分")
            return items

        # 找到新闻列表容器
        yw_list_con = yaowen_section.find('div', class_='ywListCon')
        if not yw_list_con:
            self.logger.warning("未找到新闻列表")
            return items

        # 提取每条新闻
        boxa_list = yw_list_con.find_all('div', class_='boxa')
        for rank, boxa in enumerate(boxa_list, start=1):
            try:
                # 提取标题和链接
                title_elem = boxa.find('h4').find('a')
                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')


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

