"""
36氪热搜爬虫

36氪使用字节跳动反爬SDK(TTGCaptcha)，JS会生成验证Cookie。
策略：预访问首页 → 获取服务器Set-Cookie → 请求目标页面。
偶尔仍会失败（JS生成的Cookie无法通过requests获取），属于正常现象。
"""

import time
import random
from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem


class Kr36Crawler(BaseCrawler):
    def __init__(self):
        super().__init__('kr36')

    def _get_api_url(self):
        """获取API"""
        return 'https://www.36kr.com/newsflashes/catalog/1'

    def _warmup_session(self):
        """预访问36氪首页和快讯页，获取Cookie并模拟浏览器行为"""
        try:
            # 先访问首页，让服务器种下基础Cookie
            self.session.get('https://www.36kr.com/', timeout=10,
                             allow_redirects=True)
            time.sleep(random.uniform(0.5, 1.5))
            # 再访问快讯列表页，进一步获取Cookie
            self.session.get('https://www.36kr.com/newsflashes', timeout=10,
                             allow_redirects=True)
            time.sleep(random.uniform(0.3, 1.0))
        except Exception:
            pass

    def fetch(self) -> HotSearchResult | None:
        """获取热点"""
        self.logger.info(f"正在爬取{self.platform_name}热门...")

        try:
            self._warmup_session()

            url = self._get_api_url()
            response = self._make_request(url)
            data = response.text
            items = self._parse(data)

            if not items:
                self.logger.warning(f"{self.platform_name}未解析到数据，可能被反爬拦截")

            return self._create_result(items)

        except Exception as e:
            self.logger.error(f"{self.platform_name}热门爬取失败:{e}")

    def _parse(self, html_content: str) -> List[HotSearchItem]:
        """解析API数据"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, 'html.parser')
        hot_news_items = []

        # 查找所有快讯项
        news_items = soup.find_all('div', class_='newsflash-item')

        for idx, item in enumerate(news_items, 1):
            try:
                title_elem = item.find('a', class_='item-title')
                title = title_elem.text.strip() if title_elem else ""

                url = 'https://www.36kr.com' + title_elem.get('href') if title_elem and title_elem.get('href') else None

                if not title:
                    continue

                hot_news_items.append(HotSearchItem(
                    rank=idx,
                    title=title,
                    url=url,
                ))

            except Exception as e:
                self.logger.debug(f"解析过程中发生错误: {e}")
                continue

        return hot_news_items


if __name__ == '__main__':
    crawler = Kr36Crawler()
    print(crawler.fetch())
