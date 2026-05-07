"""
全局配置设置文件
包含爬虫、请求、日志、数据存储等全局配置
"""

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path


# ==================== 路径配置 ====================
@dataclass
class PathConfig:
    """路径配置"""
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "outputs"  # 数据存储目录
    LOG_DIR: Path = BASE_DIR / "logs"  # 日志目录
    CONFIG_DIR: Path = BASE_DIR / "config"  # 配置目录
    TEMPLATES_DIR: Path = BASE_DIR / "templates"  # 模板目录
    COOKIE_DIR: Path = BASE_DIR / "crawlers" / "cookies"  # cookie目录
    DRIVER_DIR: Path = BASE_DIR / "crawlers" / "drivers"  # 浏览器驱动目录
    LLM_CACHE_DIR: Path = BASE_DIR / ".llm_cache"  # LLM分类结果缓存目录

    def create_dirs(self):
        """创建必要的目录"""
        for dir_path in [self.DATA_DIR, self.LOG_DIR, self.CONFIG_DIR, self.TEMPLATES_DIR]:
            dir_path.mkdir(exist_ok=True, parents=True)
        return self


# ==================== 请求配置 ====================
@dataclass
class RequestConfig:
    """HTTP请求配置"""

    # 基础请求头
    DEFAULT_HEADERS: Dict[str, str] = field(default_factory=lambda: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    })


    # 超时设置
    TIMEOUT: int = 30
    CONNECT_TIMEOUT: int = 10
    READ_TIMEOUT: int = 20

    # 重试设置
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 2.0
    RETRY_MULTIPLIER: float = 1.5
    RETRY_STATUS_CODES: List[int] = field(default_factory=lambda: [408, 429, 500, 502, 503, 504])

    # 并发设置
    MAX_CONCURRENT_REQUESTS: int = 5
    REQUEST_DELAY: float = 1.0  # 请求间延迟


# ==================== 日志配置 ====================
@dataclass
class LogConfig:
    """日志配置"""

    # 日志级别
    LEVEL: str = "INFO"

    # 日志格式
    FORMAT: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    DATE_FORMAT: str = '%Y-%m-%d %H:%M:%S'

    # 日志文件
    ENABLE_FILE_LOG: bool = True
    ENABLE_CONSOLE_LOG: bool = True

    # 文件日志设置
    FILE_LOG_NAME: str = "hotsearch.log"
    FILE_LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    FILE_LOG_BACKUP_COUNT: int = 5

    # 错误日志单独记录
    ERROR_LOG_NAME: str = "hotsearch_error.log"

    def get_log_file_path(self, paths: PathConfig, log_type: str = "info") -> str:
        """获取日志文件路径"""
        if log_type == "error":
            return str(paths.LOG_DIR / self.ERROR_LOG_NAME)
        return str(paths.LOG_DIR / self.FILE_LOG_NAME)



# ==================== 数据配置 ====================
@dataclass
class DataConfig:
    """数据存储和处理配置"""

    # 数据保存格式
    DEFAULT_FORMAT: str = "json"  # json, csv, parquet
    JSON_INDENT: int = 2
    JSON_ENSURE_ASCII: bool = False

    # 文件命名模式
    FILE_NAME_PATTERN: str = "{platform}_{category}_{date}_{time}.json"
    DATE_FORMAT: str = "%Y%m%d"
    TIME_FORMAT: str = "%H%M%S"

    # 数据保留策略
    MAX_FILES_PER_PLATFORM: int = 80
    CLEANUP_OLDER_THAN_DAYS: int = 30

    # 缓存控制
    ENABLE_CACHE: bool = True

    def generate_filename(self, platform: str, category: str) -> str:
        """生成文件名"""
        now = datetime.now()
        date_str = now.strftime(self.DATE_FORMAT)
        time_str = now.strftime(self.TIME_FORMAT)

        return self.FILE_NAME_PATTERN.format(
            platform=platform,
            category=category,
            date=date_str,
            time=time_str
        )

# ==================== 平台全局配置 ====================
@dataclass
class PlatformGlobalConfig:
    """平台通用配置"""

    # 默认爬取条数
    DEFAULT_FETCH_COUNT: int = 10
    MIN_FETCH_COUNT: int = 1
    MAX_FETCH_COUNT: int = 100

    # 分类显示名称
    CATEGORY_DISPLAY_NAMES: Dict[str, str] = field(default_factory=lambda: {
        'social': '社交',
        'finance': '金融',
        'tech': '科技',
        'news': '新闻',
        'entertainment': '娱乐',
    })

    # 分类颜色（用于终端显示）
    CATEGORY_COLORS: Dict[str, str] = field(default_factory=lambda: {
        'social': '\033[94m',  # 蓝色
        'finance': '\033[92m',  # 绿色
        'tech': '\033[96m',  # 青色
        'news': '\033[91m',  # 红色
        'entertainment': '\033[95m',  # 紫色
        'video': '\033[93m',  # 黄色
    })

    RESET_COLOR: str = '\033[0m'

    def get_category_color(self, category: str) -> str:
        """获取分类颜色"""
        return self.CATEGORY_COLORS.get(category, '\033[0m')

    def get_category_display_name(self, category: str) -> str:
        """获取分类显示名称"""
        return self.CATEGORY_DISPLAY_NAMES.get(category, category)


# ==================== 主配置类 ====================
@dataclass
class Settings:
    """主配置类，聚合所有配置"""

    # 项目信息
    PROJECT_NAME: str = "HotSearch Crawler"
    VERSION: str = "2.0.0"
    AUTHOR: str = "Your Name"

    # 环境
    ENVIRONMENT: str = "development"  # development, testing, production

    # 各模块配置
    paths: PathConfig = field(default_factory=PathConfig)
    request: RequestConfig = field(default_factory=RequestConfig)
    log: LogConfig = field(default_factory=LogConfig)
    data: DataConfig = field(default_factory=DataConfig)
    platform: PlatformGlobalConfig = field(default_factory=PlatformGlobalConfig)

    # 运行时配置
    _initialized: bool = False

    def __post_init__(self):
        """初始化后处理"""
        if not self._initialized:
            self.paths.create_dirs()
            self._load_environment_variables()
            self._initialized = True

    def _load_environment_variables(self):
        """从环境变量加载配置"""
        import os

        # 环境
        if env := os.getenv("HOTSEARCH_ENVIRONMENT"):
            self.ENVIRONMENT = env

        # 日志级别
        if log_level := os.getenv("HOTSEARCH_LOG_LEVEL"):
            self.log.LEVEL = log_level

    def get_data_dir(self, platform: str, category: str) -> Path:
        """获取目录"""
        data_dir = self.paths.DATA_DIR / category / platform
        data_dir.mkdir(exist_ok=True, parents=True)
        return data_dir

    def get_data_filename(self, platform: str, category: str):
        return self.data.generate_filename(platform, category)


# ==================== 单例配置实例 ====================
# 创建全局配置实例
settings = Settings()


# ==================== 配置工具函数 ====================
def get_settings() -> Settings:
    """获取配置实例（单例）"""
    return settings

