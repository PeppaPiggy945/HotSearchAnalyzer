"""
数据读取模块
用于读取指定时间范围内的 HotSearchResult 数据并转换成指定格式
"""

import json
import csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from config.settings import get_settings

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


class DataReader:
    """数据读取器"""

    def __init__(self):
        """初始化数据读取器"""
        self.settings = get_settings()
        self.data_dir = self.settings.paths.DATA_DIR / "HotSearchResult"

    def load_data(
        self,
        days: int = 1,
        platforms: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """
        读取指定时间范围内的 HotSearchResult 数据

        Args:
            days: 天数范围（默认1天）
            platforms: 平台列表（默认全部平台）
            start_date: 开始日期，格式 "YYYY-MM-DD"（可选，如果提供则忽略 days）
            end_date: 结束日期，格式 "YYYY-MM-DD"（可选，默认为今天）

        Returns:
            JSON 格式的字符串
        """
        # 计算日期范围
        if start_date and end_date:
            # 使用指定的日期范围
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        elif start_date:
            # 使用开始日期到今天
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.now()
        else:
            # 使用默认天数
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=days)

        # 确保日期精确到天（忽略时间部分）
        start_date_str = start_dt.strftime("%Y-%m-%d")
        end_date_str = end_dt.strftime("%Y-%m-%d")

        # 获取要处理的平台列表
        if platforms:
            platform_dirs = [self.data_dir / p for p in platforms if (self.data_dir / p).exists()]
        else:
            # 获取所有平台目录
            platform_dirs = [d for d in self.data_dir.iterdir() if d.is_dir()]

        # 按日期范围读取数据（每个平台每天只取最新的数据）
        result = []

        for platform_dir in platform_dirs:
            platform_key = platform_dir.name

            # 获取该平台的所有 JSON 文件
            json_files = list(platform_dir.glob("*_HotSearchResult_*.json"))

            # 按日期分组文件：{(platform, date): [file1, file2, ...]}
            date_files = {}
            for json_file in json_files:
                try:
                    filename = json_file.stem
                    parts = filename.split("_")

                    if len(parts) >= 4:
                        date_part = parts[2]  # 20260408
                        file_date = datetime.strptime(date_part, "%Y%m%d")

                        # 检查文件日期是否在范围内
                        if start_dt.date() <= file_date.date() <= end_dt.date():
                            # 以（平台，日期）作为键
                            date_key = (platform_key, file_date.date())
                            if date_key not in date_files:
                                date_files[date_key] = []
                            date_files[date_key].append((json_file, file_date))
                except Exception:
                    continue

            # 对于每个平台和日期，只选择最新的文件
            latest_files = []
            for date_key, files_list in date_files.items():
                # 按文件时间排序，取最新的
                files_list.sort(key=lambda x: x[1], reverse=True)
                latest_files.append(files_list[0][0])  # 只取最新的文件

            # 读取选中的文件
            for json_file in latest_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                        platform_name = data.get('metadata', {}).get('platform_name', platform_key)
                        fetch_time = data.get('metadata', {}).get('fetch_time', '')

                        # 从 fetch_time 提取日期部分
                        # 格式: "2026-04-08_14_34_01"
                        if fetch_time:
                            date_str = fetch_time.split('_')[0]  # 2026-04-08
                        else:
                            # 从文件名提取日期
                            filename = json_file.stem
                            parts = filename.split("_")
                            if len(parts) >= 3:
                                date_part = parts[2]
                                file_date = datetime.strptime(date_part, "%Y%m%d")
                                date_str = file_date.strftime("%Y-%m-%d")
                            else:
                                date_str = datetime.now().strftime("%Y-%m-%d")

                        # 提取 items
                        items = data.get('items', [])

                        for item in items:
                            rank = item.get('rank', 0)
                            title = item.get('title', '')

                            # 添加到结果
                            result.append({
                                "s": platform_name,
                                "d": [rank, title, date_str]
                            })

                except Exception as e:
                    print(f"读取文件 {json_file} 失败: {e}")
                    continue

        # 按平台分组
        grouped_data = self._group_by_platform(result)

        # 转换成最终的 JSON 格式
        final_result = []
        for platform_name, items in grouped_data.items():
            final_result.append({
                "s": platform_name,
                "d": items
            })

        # 返回 JSON 字符串
        return json.dumps(final_result, ensure_ascii=False, indent=2)

    def _group_by_platform(self, data: List[Dict[str, Any]]) -> Dict[str, List[List]]:
        """
        按平台分组数据

        Args:
            data: 原始数据列表

        Returns:
            按平台分组的数据字典
        """
        grouped = {}

        for item in data:
            platform_name = item['s']
            item_data = item['d']

            if platform_name not in grouped:
                grouped[platform_name] = []

            grouped[platform_name].append(item_data)

        return grouped

    def export_to_json(
        self,
        days: int = 1,
        platforms: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        output_path: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Path:
        """
        导出数据为 JSON 文件

        Args:
            days: 天数范围（默认1天）
            platforms: 平台列表（默认全部平台）
            start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
            end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
            output_path: 输出目录（默认为 outputs/exports）
            filename: 文件名（默认自动生成）

        Returns:
            导出文件的路径
        """
        # 获取数据
        data_str = self.load_data(days, platforms, start_date, end_date)
        data = json.loads(data_str)

        # 设置输出路径
        if output_path is None:
            output_path = self.settings.paths.DATA_DIR / "exports"
        else:
            output_path = Path(output_path)

        output_path.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        if filename is None:
            now = datetime.now()
            date_str = now.strftime("%Y%m%d")
            time_str = now.strftime("%H%M%S")
            filename = f"hotsearch_export_{date_str}_{time_str}.json"

        file_path = output_path / filename

        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"数据已导出到: {file_path}")
        return file_path

    def export_to_csv(
        self,
        days: int = 1,
        platforms: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        output_path: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Path:
        """
        导出数据为 CSV 文件

        Args:
            days: 天数范围（默认1天）
            platforms: 平台列表（默认全部平台）
            start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
            end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
            output_path: 输出目录（默认为 outputs/exports）
            filename: 文件名（默认自动生成）

        Returns:
            导出文件的路径
        """
        # 获取数据
        data_str = self.load_data(days, platforms, start_date, end_date)
        data = json.loads(data_str)

        # 设置输出路径
        if output_path is None:
            output_path = self.settings.paths.DATA_DIR / "exports"
        else:
            output_path = Path(output_path)

        output_path.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        if filename is None:
            now = datetime.now()
            date_str = now.strftime("%Y%m%d")
            time_str = now.strftime("%H%M%S")
            filename = f"hotsearch_export_{date_str}_{time_str}.csv"

        file_path = output_path / filename

        # 写入 CSV 文件
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            # 写入表头
            writer.writerow(['平台', '排名', '标题', '日期'])

            # 写入数据
            for platform_data in data:
                platform_name = platform_data['s']
                for item in platform_data['d']:
                    rank = item[0]
                    title = item[1]
                    date = item[2]
                    writer.writerow([platform_name, rank, title, date])

        print(f"数据已导出到: {file_path}")
        return file_path

    def export_to_excel(
        self,
        days: int = 1,
        platforms: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        output_path: Optional[str] = None,
        filename: Optional[str] = None,
        sheet_name: str = "热搜数据"
    ) -> Path:
        """
        导出数据为 Excel 文件（需要 pandas）

        Args:
            days: 天数范围（默认1天）
            platforms: 平台列表（默认全部平台）
            start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
            end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
            output_path: 输出目录（默认为 outputs/exports）
            filename: 文件名（默认自动生成）
            sheet_name: 工作表名称（默认为"热搜数据"）

        Returns:
            导出文件的路径
        """
        if not HAS_PANDAS:
            raise ImportError("需要安装 pandas 库才能导出 Excel 文件。请运行: pip install pandas openpyxl")

        # 获取数据
        data_str = self.load_data(days, platforms, start_date, end_date)
        data = json.loads(data_str)

        # 转换为扁平化数据
        flat_data = []
        for platform_data in data:
            platform_name = platform_data['s']
            for item in platform_data['d']:
                flat_data.append({
                    '平台': platform_name,
                    '排名': item[0],
                    '标题': item[1],
                    '日期': item[2]
                })

        # 创建 DataFrame
        df = pd.DataFrame(flat_data)

        # 设置输出路径
        if output_path is None:
            output_path = self.settings.paths.DATA_DIR / "exports"
        else:
            output_path = Path(output_path)

        output_path.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        if filename is None:
            now = datetime.now()
            date_str = now.strftime("%Y%m%d")
            time_str = now.strftime("%H%M%S")
            filename = f"hotsearch_export_{date_str}_{time_str}.xlsx"

        file_path = output_path / filename

        # 写入 Excel 文件
        df.to_excel(file_path, sheet_name=sheet_name, index=False, engine='openpyxl')

        print(f"数据已导出到: {file_path}")
        return file_path

    def export_all_formats(
        self,
        days: int = 1,
        platforms: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> Dict[str, Path]:
        """
        导出数据为所有格式（JSON, CSV, Excel）

        Args:
            days: 天数范围（默认1天）
            platforms: 平台列表（默认全部平台）
            start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
            end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
            output_path: 输出目录（默认为 outputs/exports）

        Returns:
            各格式导出文件的路径字典
        """
        results = {}

        # 导出 JSON
        try:
            json_path = self.export_to_json(days, platforms, start_date, end_date, output_path)
            results['json'] = json_path
        except Exception as e:
            print(f"导出 JSON 失败: {e}")

        # 导出 CSV
        try:
            csv_path = self.export_to_csv(days, platforms, start_date, end_date, output_path)
            results['csv'] = csv_path
        except Exception as e:
            print(f"导出 CSV 失败: {e}")

        # 导出 Excel
        try:
            excel_path = self.export_to_excel(days, platforms, start_date, end_date, output_path)
            results['excel'] = excel_path
        except Exception as e:
            print(f"导出 Excel 失败: {e}")

        return results

    def get_available_platforms(self) -> List[str]:
        """
        获取所有可用的平台列表

        Returns:
            平台名称列表
        """
        if not self.data_dir.exists():
            return []

        platform_dirs = [d.name for d in self.data_dir.iterdir() if d.is_dir()]
        return sorted(platform_dirs)

    def get_data_summary(self, days: int = 1) -> Dict[str, Any]:
        """
        获取数据摘要信息（每个平台每天只统计最新的文件）

        Args:
            days: 天数范围

        Returns:
            数据摘要
        """
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days)

        summary = {
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": end_dt.strftime("%Y-%m-%d"),
            "platforms": {},
            "total_records": 0
        }

        platform_dirs = [d for d in self.data_dir.iterdir() if d.is_dir()]

        for platform_dir in platform_dirs:
            platform_key = platform_dir.name
            json_files = list(platform_dir.glob("*_HotSearchResult_*.json"))

            # 按日期分组文件：{(platform, date): [file1, file2, ...]}
            date_files = {}
            for json_file in json_files:
                try:
                    filename = json_file.stem
                    parts = filename.split("_")

                    if len(parts) >= 4:
                        date_part = parts[2]
                        file_date = datetime.strptime(date_part, "%Y%m%d")

                        if start_dt.date() <= file_date.date() <= end_dt.date():
                            date_key = (platform_key, file_date.date())
                            if date_key not in date_files:
                                date_files[date_key] = []
                            date_files[date_key].append((json_file, file_date))
                except Exception:
                    continue

            # 对于每个平台和日期，只选择最新的文件
            latest_files = []
            for date_key, files_list in date_files.items():
                files_list.sort(key=lambda x: x[1], reverse=True)
                latest_files.append(files_list[0][0])

            # 统计选中文件的记录数
            record_count = 0
            file_count = len(latest_files)

            for json_file in latest_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        items = data.get('items', [])
                        record_count += len(items)
                except Exception:
                    continue

            summary["platforms"][platform_key] = {
                "files": file_count,
                "records": record_count
            }
            summary["total_records"] += record_count

        return summary


def export_data_to_json(
    days: int = 1,
    platforms: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    output_path: Optional[str] = None,
    filename: Optional[str] = None
) -> Path:
    """
    便捷函数：导出数据为 JSON 文件

    Args:
        days: 天数范围（默认1天）
        platforms: 平台列表（默认全部平台）
        start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
        end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
        output_path: 输出目录（默认为 outputs/exports）
        filename: 文件名（默认自动生成）

    Returns:
        导出文件的路径
    """
    reader = DataReader()
    return reader.export_to_json(days, platforms, start_date, end_date, output_path, filename)


def export_data_to_csv(
    days: int = 1,
    platforms: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    output_path: Optional[str] = None,
    filename: Optional[str] = None
) -> Path:
    """
    便捷函数：导出数据为 CSV 文件

    Args:
        days: 天数范围（默认1天）
        platforms: 平台列表（默认全部平台）
        start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
        end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
        output_path: 输出目录（默认为 outputs/exports）
        filename: 文件名（默认自动生成）

    Returns:
        导出文件的路径
    """
    reader = DataReader()
    return reader.export_to_csv(days, platforms, start_date, end_date, output_path, filename)


def export_data_to_excel(
    days: int = 1,
    platforms: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    output_path: Optional[str] = None,
    filename: Optional[str] = None,
    sheet_name: str = "热搜数据"
) -> Path:
    """
    便捷函数：导出数据为 Excel 文件

    Args:
        days: 天数范围（默认1天）
        platforms: 平台列表（默认全部平台）
        start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
        end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
        output_path: 输出目录（默认为 outputs/exports）
        filename: 文件名（默认自动生成）
        sheet_name: 工作表名称（默认为"热搜数据"）

    Returns:
        导出文件的路径
    """
    reader = DataReader()
    return reader.export_to_excel(days, platforms, start_date, end_date, output_path, filename, sheet_name)



def export_data_all_formats(
    days: int = 1,
    platforms: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    output_path: Optional[str] = None
) -> Dict[str, Path]:
    """
    便捷函数：导出数据为所有格式（JSON, CSV, Excel, Demo）

    Args:
        days: 天数范围（默认1天）
        platforms: 平台列表（默认全部平台）
        start_date: 开始日期，格式 "YYYY-MM-DD"（可选）
        end_date: 结束日期，格式 "YYYY-MM-DD"（可选）
        output_path: 输出目录（默认为 outputs/exports）

    Returns:
        各格式导出文件的路径字典
    """
    reader = DataReader()
    return reader.export_all_formats(days, platforms, start_date, end_date, output_path)


if __name__ == "__main__":
    # 测试代码
    reader = DataReader()

    # 打印可用平台
    print("=" * 60)
    print("可用平台:")
    platforms = reader.get_available_platforms()
    for p in platforms:
        print(f"  - {p}")

    # 打印数据摘要
    print("\n" + "=" * 60)
    print("数据摘要（最近1天，已去重，每个平台每天只取最新数据）:")
    summary = reader.get_data_summary(days=1)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # 读取 demo 格式数据
    print("\n" + "=" * 60)
    print("读取 demo 格式数据（最近1天，已去重）:")
    demo_data = reader.load_data(days=1)
    print(demo_data[:500] + "..." if len(demo_data) > 500 else demo_data)

    # 测试导出功能
    print("\n" + "=" * 60)
    print("测试导出功能（已去重数据）:")

    try:
        # 导出为 JSON
        json_path = reader.export_to_json(days=1)
        print(f"✓ JSON 导出成功: {json_path}")

        # 导出为 CSV
        csv_path = reader.export_to_csv(days=1)
        print(f"✓ CSV 导出成功: {csv_path}")

        # 导出为 Excel
        try:
            excel_path = reader.export_to_excel(days=1)
            print(f"✓ Excel 导出成功: {excel_path}")
        except ImportError as e:
            print(f"✗ Excel 导出失败（需要安装 pandas）: {e}")

    except Exception as e:
        print(f"✗ 导出失败: {e}")

    # 测试便捷函数
    print("\n" + "=" * 60)
    print("测试便捷导出函数:")

    try:
        json_path = export_data_to_json(days=1, filename="test_export.json")
        print(f"✓ 便捷函数 JSON 导出成功: {json_path}")

        csv_path = export_data_to_csv(days=1, filename="test_export.csv")
        print(f"✓ 便捷函数 CSV 导出成功: {csv_path}")
    except Exception as e:
        print(f"✗ 便捷函数导出失败: {e}")

    print("\n" + "=" * 60)
    print("测试完成!")
