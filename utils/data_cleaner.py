"""
数据清理工具
基于连续密度函数清理热搜数据文件

核心思想：
  想象时间轴上的一组采样点 —— 近端密集、远端稀疏、平滑过渡。
  密度函数 f(t) 定义了每个"天数年龄" t 允许保留的文件数：
    f(0)         = max_per_platform   (今天，最密集)
    f(keep_days) = 0                  (超出保留期，全部删除)

  清理分两级：
    宏观：f(天数年龄) → 该天允许保留的文件数
    微观：在该天内部，用分层抽样按密度函数选取文件，而非简单截断最新的 N 个
"""

import re
import math
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from core.logger import get_logger

logger = get_logger(__name__)

# 文件名日期模式：_YYYYMMDD_HHMMSS
_FILENAME_DT_RE = re.compile(r'_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})')


def _parse_datetime(fpath: Path):
    """从文件名提取日期时间，失败则回退到 st_mtime"""
    m = _FILENAME_DT_RE.search(fpath.name)
    if m:
        try:
            return datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)), int(m.group(6)),
            )
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(fpath.stat().st_mtime)
    except OSError:
        return None


def density_function(t, keep_days, max_per_platform):
    """
    密度函数 f(t)：给定天数年龄 t，返回该时间点的密度值（文件数）。

    f(0) = max_per_platform, f(keep_days) = 0
    指数衰减平滑过渡。

    示例 (keep_days=30, max=80):
      t=0   → 80  (今天)
      t=7   → 54
      t=14  → 36
      t=21  → 23
      t=29  → 8
    """
    if t < 0:
        return max_per_platform
    if t >= keep_days:
        return 0
    if keep_days <= 1:
        return max_per_platform

    x = t / keep_days
    raw = max_per_platform * math.exp(-3.0 * x)
    return max(1, round(raw))


def _select_by_density(day_files, daily_limit):
    """
    微观选取：从一天内的文件中按密度函数选取 daily_limit 个文件。

    使用分层抽样 (stratified sampling)：
      1. 将每个文件映射到密度函数的 CDF 上
      2. 将 CDF 等分为 daily_limit 个区间
      3. 每个区间取距离中点最近的文件

    效果：选出的文件在时间上自然形成「近端密集、远端稀疏」的分布，
    而非简单截断最新 N 个（后者会丢失整天前半段的全部数据）。

    Args:
        day_files: [(filepath, datetime), ...] 该天的所有文件
        daily_limit: 允许保留的文件数

    Returns:
        选取后的 [(filepath, datetime), ...]
    """
    n = len(day_files)
    if n <= daily_limit:
        return day_files

    day_files_sorted = sorted(day_files, key=lambda x: x[1])

    if n == 1 or daily_limit <= 0:
        return day_files_sorted[:max(0, daily_limit)]

    # ── 计算每个文件的密度 ──
    # position ∈ [0, 1]：0=该天最早，1=该天最晚
    # age ∈ [0, 1]：0=最新（近端），1=最早（远端）
    densities = []
    for i in range(n):
        age = 1.0 - i / (n - 1) if n > 1 else 0.0
        densities.append(density_function(age, 1.0, daily_limit))

    # ── 构建 CDF ──
    total = sum(densities)
    if total <= 0:
        # 极端情况：均匀选取
        step = n / daily_limit
        return [day_files_sorted[min(int(i * step), n - 1)] for i in range(daily_limit)]

    cdf = []
    cum = 0.0
    for d in densities:
        cum += d / total
        cdf.append(cum)
    cdf[-1] = 1.0

    # ── 分层抽样 ──
    kept = set()
    for k in range(daily_limit):
        target_q = (k + 0.5) / daily_limit
        best_i = -1
        best_dist = float('inf')
        for i in range(n):
            if i in kept:
                continue
            dist = abs(cdf[i] - target_q)
            if dist < best_dist:
                best_dist = dist
                best_i = i
        if best_i >= 0:
            kept.add(best_i)

    return [day_files_sorted[i] for i in sorted(kept)]


def cleanup_outputs(
    outputs_dir: str,
    category: str = "HotSearchResult",
    max_files_per_platform: int = 80,
    cleanup_older_than_days: int = 30,
) -> int:
    """
    基于密度函数清理数据文件。

    对每个平台：
      1. 收集所有文件，从文件名提取采集日期
      2. 按日期分组，计算每天的天数年龄 t
      3. 调用密度函数 f(t) 得到该天允许保留的文件数（宏观）
      4. 该天内用分层抽样按密度函数选取文件（微观）
      5. 删除未选中的文件

    Args:
        outputs_dir: 输出根目录路径
        category: 数据分类目录名
        max_files_per_platform: 密度函数近端上限
        cleanup_older_than_days: 保留天数

    Returns:
        删除的文件数量
    """
    category_dir = Path(outputs_dir) / category

    if not category_dir.exists():
        logger.debug(f"数据目录不存在，跳过清理: {category_dir}")
        return 0

    deleted_count = 0
    today = datetime.now()

    for platform_dir in sorted(category_dir.iterdir()):
        if not platform_dir.is_dir():
            continue

        # 收集所有文件及其采集时间
        files = []
        for f in platform_dir.iterdir():
            if not f.is_file():
                continue
            dt = _parse_datetime(f)
            if dt is not None:
                files.append((f, dt))

        if not files:
            continue

        # 按日期分组
        date_groups = defaultdict(list)
        for fpath, dt in files:
            date_groups[dt.date()].append((fpath, dt))

        # 按日期从新到旧处理
        sorted_dates = sorted(date_groups.keys(), reverse=True)

        for date_key in sorted_dates:
            age_days = (today.date() - date_key).days
            daily_limit = density_function(age_days, cleanup_older_than_days, max_files_per_platform)

            day_files = date_groups[date_key]

            if daily_limit <= 0:
                # 超出保留期，全部删除
                for fpath, _ in day_files:
                    try:
                        fpath.unlink()
                        deleted_count += 1
                        logger.debug(f"[超龄] 删除: {fpath.name} ({date_key}, {age_days}天前)")
                    except OSError as e:
                        logger.warning(f"删除文件失败: {fpath}, {e}")
                continue

            # 微观：按密度函数选取文件
            kept = _select_by_density(day_files, daily_limit)
            kept_paths = {fpath for fpath, _ in kept}

            for fpath, _ in day_files:
                if fpath not in kept_paths:
                    try:
                        fpath.unlink()
                        deleted_count += 1
                        logger.debug(
                            f"[密度] 删除: {fpath.name} ({date_key}, "
                            f"{age_days}天前, 保留 {daily_limit}/{len(day_files)})"
                        )
                    except OSError as e:
                        logger.warning(f"删除文件失败: {fpath}, {e}")

    if deleted_count > 0:
        logger.info(f"数据清理完成: 共删除 {deleted_count} 个文件")
    else:
        logger.debug("数据清理完成: 无需删除文件")

    return deleted_count
