#!/usr/bin/env python3
"""
Cookie提取工具（纯HTTP版，无浏览器依赖）

通过模拟微博访客认证API获取Cookie：
  1. GET weibo.com → 触发visitor重定向，获取初始Cookie
  2. POST genvisitor2 → 获取SUB/SUBP等关键Cookie
无需 Selenium、浏览器、WebDriver。
"""

import json
import os
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse
import requests
import logging
from config.settings import get_settings
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 默认请求头，模拟正常浏览器
_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
       'AppleWebKit/537.36 (KHTML, like Gecko) '
       'Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0')
_DEFAULT_HEADERS = {
    'User-Agent': _UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
}

# 微博访客认证专用
_WEIBO_VISITOR_INIT_URL = 'https://www.weibo.com'
_WEIBO_GENVISITOR_URL = 'https://passport.weibo.com/visitor/genvisitor2'
_WEIBO_REFERER = 'https://passport.weibo.com/visitor/visitor'


def _cookies_to_list(session: requests.Session) -> List[Dict]:
    """将session中的cookie转为标准列表格式"""
    return [
        {
            'name': c.name,
            'value': c.value,
            'domain': c.domain,
            'path': c.path,
            'secure': c.secure,
        }
        for c in session.cookies
    ]


def _get_weibo_cookies() -> Optional[List[Dict]]:
    """
    通过微博访客认证API获取Cookie

    流程:
      1. GET weibo.com → 触发重定向到visitor页面，获取XSRF-TOKEN
      2. POST genvisitor2 → 通过Set-Cookie获取SUB、SUBP等关键Cookie
    """
    session = requests.Session()
    session.headers.update(_DEFAULT_HEADERS)

    # 步骤1: 访问weibo.com触发visitor重定向
    try:
        resp = session.get(_WEIBO_VISITOR_INIT_URL, timeout=15, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"访问weibo.com失败: {e}")
        return None

    # 步骤2: 调用genvisitor2获取SUB/SUBP
    try:
        resp2 = session.post(
            _WEIBO_GENVISITOR_URL,
            params={'cb': 'gen_visitor_callback', 'a': 'enter'},
            data={'sp': str(int(time.time() * 1000))},
            headers={
                'Referer': _WEIBO_REFERER,
                'Origin': 'https://passport.weibo.com',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            timeout=15,
        )
        resp2.raise_for_status()

        # 检查返回是否成功
        match = re.search(r'gen_visitor_callback\((.*)\)', resp2.text)
        if match:
            api_data = json.loads(match.group(1))
            if api_data.get('retcode') != 20000000:
                logger.warning(f"genvisitor2返回异常: {api_data}")
    except requests.RequestException as e:
        logger.error(f"调用genvisitor2失败: {e}")
        return None

    cookies = _cookies_to_list(session)
    has_sub = any(c['name'] == 'SUB' for c in cookies)

    if not has_sub:
        logger.warning("未获取到SUB Cookie，认证可能失败")
    else:
        logger.info(f"成功获取 {len(cookies)} 个Cookie（含SUB）")

    return cookies if cookies else None


def get_file_path(filename: str) -> Path:
    """cookie相关文件路径"""
    filepath = get_settings().paths.COOKIE_DIR / filename
    return filepath


def turn_cookies_list(cookies_list: List[Dict]) -> Dict[str, str]:
    """将cookie列表转为 {name: value} 字典"""
    if cookies_list:
        return {c['name']: c['value'] for c in cookies_list}
    return {}


def get_cookies_from_file(filename: str) -> List[Dict]:
    """从JSON文件读取缓存的cookie列表"""
    cookies_list = []
    filepath = get_file_path(filename)
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                cookies_list = json.load(file)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"读取cookie文件失败: {e}")
    return cookies_list


def get_website_cookies(
        url: str,
        driver_path: str = None,
        headless: bool = True,
        wait_time: int = 5,
        save_to_file: bool = False,
        filename: str = None
) -> Optional[List[Dict]]:
    """
    获取网站Cookie（纯HTTP，无需浏览器）

    对于微博域名，使用访客认证API获取SUB/SUBP等Cookie；
    对于其他域名，直接发HTTP请求收集Set-Cookie。

    参数:
        url: 要访问的网址
        save_to_file: 是否保存到文件
        filename: 保存的文件名

    返回:
        Cookie列表 或 None
    """
    cookies = None

    # 微博域名走专用访客认证流程
    if 'weibo.com' in url:
        cookies = _get_weibo_cookies()
    else:
        try:
            session = requests.Session()
            session.headers.update(_DEFAULT_HEADERS)
            resp = session.get(url, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            cookies = _cookies_to_list(session)
            logger.info(f"获取到 {len(cookies)} 个Cookie")
        except requests.RequestException as e:
            logger.error(f"HTTP请求获取Cookie失败: {e}")
            return None

    # 保存到文件
    if cookies and save_to_file:
        if filename is None:
            domain = urlparse(url).netloc.replace(".", "_")
            filename = f"cookies_{domain}.json"
        filepath = get_file_path(filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        logger.info(f"Cookie已保存到: {filepath}")

    return cookies


def get_cookies_simple(url: str) -> Optional[List[Dict]]:
    """最简单的Cookie获取函数"""
    return get_website_cookies(url)


class CookieExtractor:
    """
    Cookie提取器（纯HTTP版）

    保持与原 Selenium 版本相同的接口，但内部使用 requests 实现，
    不需要任何浏览器或 WebDriver。
    """

    def __init__(
            self,
            driver_path: str = None,
            headless: bool = True,
            user_data_dir: str = None,
            implicit_wait: int = 10
    ):
        self.session = requests.Session()
        self.session.headers.update(_DEFAULT_HEADERS)
        logger.info("CookieExtractor 初始化完成（纯HTTP模式，无需浏览器）")

    def get_cookies(
            self,
            url: str,
            wait_time: int = 5,
            element_wait: str = None
    ) -> Optional[List[Dict]]:
        """获取指定网站的Cookie"""
        return get_website_cookies(url)

    def get_cookies_dict(self, url: str, **kwargs) -> Dict[str, str]:
        """获取Cookie字典格式（name: value）"""
        cookies = self.get_cookies(url, **kwargs)
        if cookies:
            return {c['name']: c['value'] for c in cookies}
        return {}

    def save_cookies(
            self,
            url: str,
            filename: str = None,
            format: str = 'json',
            **kwargs
    ) -> bool:
        """获取并保存Cookie到文件"""
        cookies = self.get_cookies(url, **kwargs)

        if not cookies:
            logger.error("未获取到Cookie，保存失败")
            return False

        if filename is None:
            domain = urlparse(url).netloc.replace(".", "_")
            filename = f"cookies_{domain}.{format}"
        filepath = get_file_path(filename)

        try:
            if format.lower() == 'json':
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                logger.info(f"Cookie已保存为JSON: {filepath}")
            elif format.lower() == 'txt':
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# Cookies from {url}\n")
                    f.write(f"# Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# Total: {len(cookies)} cookies\n\n")
                    for i, cookie in enumerate(cookies, 1):
                        f.write(f"[Cookie {i}]\n")
                        f.write(f"Name: {cookie['name']}\n")
                        f.write(f"Value: {cookie['value']}\n")
                        f.write(f"Domain: {cookie.get('domain', 'N/A')}\n")
                        f.write(f"Path: {cookie.get('path', '/')}\n")
                        f.write("-" * 40 + "\n")
                logger.info(f"Cookie已保存为TXT: {filepath}")
            else:
                logger.error(f"不支持的格式: {format}")
                return False
            return True

        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            return False

    def get_cookie_header(self, url: str, **kwargs) -> str:
        """获取Cookie请求头格式"""
        cookies = self.get_cookies(url, **kwargs)
        if cookies:
            return "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        return ""

    def get_cookies_for_requests(self, url: str, **kwargs) -> Dict[str, str]:
        """获取requests库可用的Cookie字典"""
        return self.get_cookies_dict(url, **kwargs)

    def close(self) -> None:
        """关闭会话"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()
