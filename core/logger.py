"""
统一日志模块
提供简洁的日志功能，基于 settings.py 中的配置
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional
from pathlib import Path

from config.settings import get_settings


class LoggerManager:
    """日志管理器（单例模式）"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._setup_loggers()
            LoggerManager._initialized = True

    def _setup_loggers(self):
        """初始化日志系统"""
        settings = get_settings()
        log_config = settings.log
        paths = settings.paths

        # 确保日志目录存在
        paths.LOG_DIR.mkdir(exist_ok=True, parents=True)

        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_config.LEVEL.upper(), logging.INFO))

        # 清除现有的处理器
        root_logger.handlers.clear()

        # 添加控制台处理器
        if log_config.ENABLE_CONSOLE_LOG:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, log_config.LEVEL.upper(), logging.INFO))
            console_formatter = logging.Formatter(
                log_config.FORMAT,
                datefmt=log_config.DATE_FORMAT
            )
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)

        # 添加文件处理器
        if log_config.ENABLE_FILE_LOG:
            # 普通日志文件
            file_handler = RotatingFileHandler(
                filename=log_config.get_log_file_path(paths, "info"),
                maxBytes=log_config.FILE_LOG_MAX_BYTES,
                backupCount=log_config.FILE_LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setLevel(getattr(logging, log_config.LEVEL.upper(), logging.INFO))
            file_formatter = logging.Formatter(
                log_config.FORMAT,
                datefmt=log_config.DATE_FORMAT
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)

            # 错误日志文件（只记录错误及以上级别）
            error_handler = RotatingFileHandler(
                filename=log_config.get_log_file_path(paths, "error"),
                maxBytes=log_config.FILE_LOG_MAX_BYTES,
                backupCount=log_config.FILE_LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_formatter = logging.Formatter(
                log_config.FORMAT,
                datefmt=log_config.DATE_FORMAT
            )
            error_handler.setFormatter(error_formatter)
            root_logger.addHandler(error_handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取日志记录器

    Args:
        name: 日志记录器名称，通常使用 __name__

    Returns:
        Logger 实例

    Examples:
        >>> from core.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("这是一条信息")
        >>> logger.error("这是一条错误")
    """
    # 确保日志系统已初始化
    LoggerManager()

    # 获取或创建日志记录器
    if name:
        logger = logging.getLogger(name)
    else:
        logger = logging.getLogger()

    return logger
