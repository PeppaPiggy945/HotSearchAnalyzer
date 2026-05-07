# analytics/data_loader.py
"""
热搜数据加载模块
负责读取各平台爬取的热搜 JSON 数据，并与前一天数据比对标记新内容。
"""

import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

from core.models import HotSearchInfo

try:
    import jieba
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False


class DataLoader:
    """热搜数据加载器"""

    def __init__(self, data_dir: Path, use_nlp: bool = True):
        self.data_dir = data_dir
        self.use_nlp = use_nlp and NLP_AVAILABLE

    def load(self) -> List[HotSearchInfo]:
        """加载所有平台最新热搜数据，标记是否为新内容"""
        if not self.data_dir.exists():
            print(f"数据目录不存在: {self.data_dir}")
            return []

        latest_files = self._get_latest_files()
        previous_hour_files = self._get_previous_hour_files()
        previous_day_data = self._load_previous_data(previous_hour_files)

        hotsearch_list: List[HotSearchInfo] = []
        for _, json_file in latest_files.items():
            hotsearch_list.extend(self._load_platform_file(json_file, previous_day_data))

        new_count = sum(1 for hs in hotsearch_list if hs.is_new)
        print(f"成功加载 {len(hotsearch_list)} 条热搜数据（其中 {new_count} 条为新内容）")
        return hotsearch_list

    # ------------------------------------------------------------------
    #  Private
    # ------------------------------------------------------------------

    def _load_platform_file(self, json_file: Path, previous_day_data: List[Dict]) -> List[HotSearchInfo]:
        results: List[HotSearchInfo] = []
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                metadata = data.get('metadata', {})
                for item in data.get('items', []):
                    title = item.get('title', '')
                    platform = metadata.get('platform', '')
                    results.append(HotSearchInfo(
                        title=title,
                        url=item.get('url', ''),
                        platform=platform,
                        platform_name=metadata.get('platform_name', ''),
                        rank=item.get('rank', 0),
                        category=metadata.get('category', ''),
                        sub_category=metadata.get('sub_category', ''),
                        fetch_time=metadata.get('fetch_time', ''),
                        is_new=self._is_new_content(title, platform, previous_day_data),
                    ))
        except Exception as e:
            print(f"读取文件失败 {json_file}: {e}")
        return results

    def _load_previous_data(self, previous_day_files: Dict[str, Path]) -> List[Dict]:
        prev: List[Dict] = []
        for _, json_file in previous_day_files.items():
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    meta = data.get('metadata', {})
                    for item in data.get('items', []):
                        prev.append({
                            'title': item.get('title', ''),
                            'platform': meta.get('platform', ''),
                        })
            except Exception as e:
                print(f"读取前一天文件失败 {json_file}: {e}")
        return prev

    def _get_latest_files(self) -> Dict[str, Path]:
        latest: Dict[str, Path] = {}
        for d in self.data_dir.iterdir():
            if not d.is_dir():
                continue
            files = list(d.glob("*.json"))
            if files:
                latest[d.name] = max(files, key=lambda x: x.name)
        return latest

    @staticmethod
    def _parse_file_datetime(filepath: Path) -> datetime | None:
        """从文件名解析完整时间：{platform}_HotSearchResult_{YYYYMMDD}_{HHMMSS}.json"""
        parts = filepath.stem.split("_")
        if len(parts) >= 3 and len(parts[2]) == 8 and parts[2].isdigit():
            try:
                d = datetime.strptime(parts[2], "%Y%m%d")
                if len(parts) >= 4 and len(parts[3]) == 6 and parts[3].isdigit():
                    t = parts[3]
                    return datetime(d.year, d.month, d.day,
                                    int(t[:2]), int(t[2:4]), int(t[4:6]))
                return d
            except ValueError:
                pass
        return None

    def _get_previous_hour_files(self) -> Dict[str, Path]:
        """获取各平台前1小时的数据文件（最接近最新文件1小时前的文件）"""
        result: Dict[str, Path] = {}
        for d in self.data_dir.iterdir():
            if not d.is_dir():
                continue
            files = list(d.glob("*.json"))
            if not files:
                continue
            parsed = [(dt, f) for f in files if (dt := self._parse_file_datetime(f)) is not None]
            if not parsed:
                continue
            parsed.sort(key=lambda x: x[0], reverse=True)
            latest_dt = parsed[0][0]
            target = latest_dt - timedelta(hours=1)
            best, best_diff = None, None
            for dt, f in parsed[1:]:
                diff = abs((dt - target).total_seconds())
                if best_diff is None or diff < best_diff:
                    best_diff, best = diff, f
            if best is not None and best_diff <= 7200:
                result[d.name] = best
        return result

    def _is_new_content(self, title: str, platform: str, previous_day_data: List[Dict]) -> bool:
        if not previous_day_data:
            return True

        same_plat: List[Dict] = []
        cross_plat: List[Dict] = []
        for item in previous_day_data:
            (same_plat if item['platform'] == platform else cross_plat).append(item)

        # 1. 精确匹配（同平台）
        for item in same_plat:
            if item['title'] == title:
                return False

        # 预分词
        if self.use_nlp:
            title_words = set(jieba.cut(title))
        else:
            title_words = set(re.findall(r'\w+', title))
        if not title_words:
            return True

        # 2. 相似度匹配（同平台，阈值 0.85）
        for item in same_plat:
            other = set(jieba.cut(item['title'])) if self.use_nlp else set(re.findall(r'\w+', item['title']))
            if other:
                inter, union = len(title_words & other), len(title_words | other)
                if union > 0 and inter / union >= 0.85:
                    return False

        # 3. 跨平台相似度匹配（阈值 0.80）
        for item in cross_plat:
            other = set(jieba.cut(item['title'])) if self.use_nlp else set(re.findall(r'\w+', item['title']))
            if other:
                inter, union = len(title_words & other), len(title_words | other)
                if union > 0 and inter / union >= 0.80:
                    return False

        return True
