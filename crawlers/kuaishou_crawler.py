"""
快手热门爬虫
"""

import json
import re
from typing import List
from crawlers.base_crawler import BaseCrawler
from core.models import HotSearchResult, HotSearchItem


class KuaishouCrawler(BaseCrawler):
    def __init__(self):
        super().__init__('kuaishou')

    def _get_api_url(self):
        """获取API"""
        return 'https://www.kuaishou.com/?isHome=1&source=NewReco'

    def fetch(self) -> HotSearchResult | None:
        """获取快手热门"""
        self.logger.info(f"正在爬取{self.platform_name}热门...")

        try:
            url = self._get_api_url()
            response = self._make_request(url)
            html_text = response.text
            items = self._parse(html_text)
            return self._create_result(items)

        except Exception as e:
            self.logger.error(f"{self.platform_name}热门爬取失败: {e}")

    def _parse(self, html_text: str) -> List[HotSearchItem]:
        """解析API数据"""
        hot_items = []

        try:
            # 在HTML中查找包含VisionHotRankItem的JSON数据
            # 快手的数据通常在__NEXT_DATA__或script标签中
            pattern = r'"VisionHotRankItem:([^"]+)"\s*:\s*({[^}]*"rank"\s*:\s*\d+[^}]*})'
            matches = re.findall(pattern, html_text)

            for match in matches:
                try:
                    # 解析每个热点项的JSON数据
                    key, item_json = match
                    item_data = json.loads(item_json)

                    # 提取字段
                    rank = item_data.get("rank", 0)
                    # rank从0开始，实际排名是rank+1
                    actual_rank = rank + 1
                    title = item_data.get("name", "")
                    hot_value = item_data.get("hotValue")
                    tag_type = item_data.get("tagType", "")
                    poster = item_data.get("poster", "")

                    # 只处理有效数据
                    if not title:
                        continue

                    # 构造URL（如果需要）
                    url = f"https://www.kuaishou.com/search?keyword={title}"

                    # 创建热搜项
                    hot_item = HotSearchItem(
                        rank=actual_rank,
                        title=title,
                        url=url
                    )

                    hot_items.append(hot_item)

                except Exception as e:
                    self.logger.debug(f"解析{self.platform_name}单个热点项失败: {e}")
                    continue

            # 如果没有找到匹配项，尝试另一种解析方式
            if not hot_items:
                # 尝试查找更大的JSON块
                pattern2 = r'VisionHotRankItem[^{]*{[^}]*"rank"[^}]*}[^}]*}'
                matches2 = re.findall(pattern2, html_text)
                
                for item_str in matches2:
                    try:
                        # 尝试提取基本字段
                        rank_match = re.search(r'"rank"\s*:\s*(\d+)', item_str)
                        name_match = re.search(r'"name"\s*:\s*"([^"]+)"', item_str)
                        
                        if rank_match and name_match:
                            rank = int(rank_match.group(1))
                            actual_rank = rank + 1
                            title = name_match.group(1)
                            
                            hot_item = HotSearchItem(
                                rank=actual_rank,
                                title=title,
                                url=f"https://www.kuaishou.com/search?keyword={title}"
                            )
                            hot_items.append(hot_item)
                    
                    except Exception as e:
                        self.logger.debug(f"使用第二种方式解析{self.platform_name}热点项失败: {e}")
                        continue

            # 按排名排序
            hot_items.sort(key=lambda x: x.rank)

        except Exception as e:
            self.logger.error(f"解析{self.platform_name}热门数据失败: {e}")

        return hot_items

