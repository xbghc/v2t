"""日志配置模块"""

import logging
import os
import sys

from loguru import logger


def _is_dev_mode() -> bool:
    """判断是否为开发环境"""
    debug = os.environ.get("DEBUG", "").lower()
    if debug in ("1", "true", "yes"):
        return True
    # stderr 是 TTY 时视为开发环境
    return sys.stderr.isatty()


def setup_logging() -> None:
    """配置日志"""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    is_dev = _is_dev_mode()

    logger.remove()

    if is_dev:
        # 开发环境：彩色文本
        logger.add(
            sys.stderr,
            level=log_level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
            colorize=True,
        )
    else:
        # 生产环境：JSON 格式
        logger.add(
            sys.stderr,
            level=log_level,
            format="{message}",
            serialize=True,  # loguru 内置 JSON 序列化
        )

    # 拦截标准 logging
    _intercept_standard_logging()


def _intercept_standard_logging() -> None:
    """拦截标准 logging 输出到 loguru"""

    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            try:
                lvl = logger.level(record.levelname).name
            except ValueError:
                lvl = record.levelno
            frame, depth = sys._getframe(6), 6
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
            logger.opt(depth=depth, exception=record.exc_info).log(
                lvl, record.getMessage()
            )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
