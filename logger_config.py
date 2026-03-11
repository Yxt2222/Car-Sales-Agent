"""
日志配置模块 - 统一设置应用日志
用途：追踪 Agent 行为，便于调试和分析攻击效果
"""

import logging
import sys
from pathlib import Path

from config import LogConfig


def setup_logging():
    """
    设置应用日志系统

    配置包括：
    - 控制台输出（彩色）
    - 文件输出（持久化）
    - 不同级别的日志过滤
    """
    # 创建日志目录
    log_dir = LogConfig.LOG_FILE.parent
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)

    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LogConfig.LOG_LEVEL))

    # 清除现有处理器（避免重复添加）
    root_logger.handlers.clear()

    # 定义日志格式
    formatter = logging.Formatter(LogConfig.LOG_FORMAT)

    # 1. 控制台处理器（彩色输出）
    if LogConfig.LOG_TO_CONSOLE:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)  # 控制台只显示 INFO 及以上
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 2. 文件处理器（持久化）
    file_handler = logging.FileHandler(
        LogConfig.LOG_FILE,
        encoding="utf-8",
        mode="a"  # 追加模式
    )
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    logging.info("=" * 50)
    logging.info("日志系统已启动")
    logging.info(f"日志级别: {LogConfig.LOG_LEVEL}")
    logging.info(f"日志文件: {LogConfig.LOG_FILE}")
    logging.info("=" * 50)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志记录器

    Args:
        name: 日志记录器名称（通常使用 __name__）

    Returns:
        日志记录器对象
    """
    return logging.getLogger(name)


# 自动初始化（模块导入时执行）
setup_logging()
