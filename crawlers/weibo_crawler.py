"""
热搜爬虫
"""

from typing import List, Optional, Dict, Any
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem
from bs4 import BeautifulSoup
import re
from crawlers.cookies.cookie_extractor import get_website_cookies, get_cookies_from_file, turn_cookies_list



class WeiboCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('weibo')


    def _get_api_url(self):
        """获取API"""
        return 'https://s.weibo.com/top/summary'


    def _get_cookies(self, get_new=False):
        # 获取Cookie字典
        cookie_file = f"{self.platform_key}_cookies.json"
        cookies_list = []
        if not get_new:
            cookies_list = get_cookies_from_file(cookie_file)
        if not cookies_list:
            cookies_list = get_website_cookies("https://www.weibo.com", headless=True, wait_time=3, save_to_file=True, filename=cookie_file)
        cookies_dict = turn_cookies_list(cookies_list)
        return cookies_dict



    def fetch(self) -> HotSearchResult | None:
        """获取热搜"""

        self.logger.info(f"正在爬取{self.platform_name}热门...")

        try:
            # 热门API
            url = self._get_api_url()
            cookies_dict = self._get_cookies(get_new=False)
            response = self._make_request(url, cookies=cookies_dict)
            try:
                items = self._parse(response.content.decode('utf-8'))
            except Exception as e:
                self.logger.warning("本地cookie无效，尝试重新获取")
                cookies_dict = self._get_cookies(get_new=True)
                response = self._make_request(url, cookies=cookies_dict)
                items = self._parse(response.content.decode('utf-8'))
            return self._create_result(items)

        except Exception as e:
            self.logger.error(f"{self.platform_name}热门爬取失败:{e}")


    def _parse(self, html_text: str) -> List[HotSearchItem]:
        """解析API数据"""
        soup = BeautifulSoup(html_text, 'html.parser')
        hot_items: List[HotSearchItem] = []

        for tr in soup.find_all('tr'):
            # 1. 提取排名
            rank: Optional[int] = None
            rank_td = tr.find('td', class_=re.compile(r'td-01'))
            if rank_td:
                rank_text = rank_td.get_text(strip=True)
                if rank_text.isdigit():
                    rank = int(rank_text)

            # 2. 提取标题、链接、热度值
            title: str = ''
            url: Optional[str] = None
            hot_value: Optional[int] = None
            raw_hot_text: str = ''  # 用于存放原始的span文本，可能包含“剧集”等额外信息

            td_02 = tr.find('td', class_='td-02')
            if td_02:
                # 提取标题和链接
                a_tag = td_02.find('a')
                if a_tag:
                    title = a_tag.get_text(strip=True)
                    url = f'https://s.weibo.com{a_tag.get('href')}'

                # 提取热度值（讨论量）
                span_tag = td_02.find('span')
                if span_tag:
                    raw_hot_text = span_tag.get_text(strip=True)
                    numbers = re.findall(r'\d+', raw_hot_text)
                    if numbers:
                        hot_value = int(numbers[0])

            # 3. 提取标签（热度标识，如“新”）
            label: str = ''
            td_03 = tr.find('td', class_='td-03')
            if td_03:
                i_tag = td_03.find('i')
                if i_tag:
                    label = i_tag.get_text(strip=True)

            # 4. 构建extra字典，存放原始数据中的额外信息
            extra: Optional[Dict[str, Any]] = None
            # 示例：如果原始热度文本包含非数字信息（如“剧集”），则存入extra
            if raw_hot_text and not re.fullmatch(r'\d+', raw_hot_text.strip()):
                extra = {
                    'raw_hot_indicator': raw_hot_text,
                    'hot_value': hot_value,
                    'label': label if label else None
                }
                # 这里可以放入更多从原始HTML中解析出的、但未在主要字段中体现的信息

            # 只有当成功提取到排名和标题时，才创建对象
            if rank is not None and title:
                item = HotSearchItem(
                    rank=rank,
                    title=title,
                    url=url,  # 空字符串转为None以符合Optional类型
                )
                hot_items.append(item)

        return hot_items


    def get_description(self) -> str:
        return "爬取{self.platform}热门视频，包含播放量、点赞数等数据"
