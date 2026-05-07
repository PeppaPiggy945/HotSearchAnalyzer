"""
爬虫模块初始化文件
"""

from crawlers.base_crawler import BaseCrawler, HotSearchItem, HotSearchResult
from crawlers.crawler_factory import HotSearchCrawlerFactory
from crawlers.weibo_crawler import WeiboCrawler
from crawlers.zhihu_crawler import ZhihuCrawler
from crawlers.douyin_crawler import DouyinCrawler
from crawlers.bilibili_crawler import BilibiliCrawler
from crawlers.toutiao_crawler import ToutiaoCrawler
from crawlers.huxiu_crawler import HuxiuCrawler
from crawlers.wallstreetcn_crawler import WallCrawler
from crawlers.cctv_crawler import CCTVNewsCrawler
from crawlers.peopledaily_crawler import PeopleDailyCrawler
from crawlers.kr36_crawler import Kr36Crawler
from crawlers.sina_crawler import SinaCrawler
from crawlers.wechat_crawler import WeChatCrawler
from crawlers.tencentnews_crawler import TencentNewsCrawler
from crawlers.tieba_crawler import TiebaCrawler


__all__ = [
    'BaseCrawler',
    'HotSearchItem',
    'HotSearchResult',
    'HotSearchCrawlerFactory',
    'WeiboCrawler',
    'ZhihuCrawler',
    'DouyinCrawler',
    'BilibiliCrawler',
    'ToutiaoCrawler',
    'HuxiuCrawler',
    'WallCrawler',
    'CCTVNewsCrawler',
    'PeopleDailyCrawler',
    'Kr36Crawler',
    'SinaCrawler',
    'WeChatCrawler',
    'TencentNewsCrawler',
    'TiebaCrawler',
]