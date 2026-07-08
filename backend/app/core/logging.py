"""
Structured logging configuration. Uses loguru for readable, leveled logs
with rotation, and exposes a `get_logger` helper for module-level loggers.
"""
import sys

from loguru import logger

from app.core.config import settings

logger.remove()
logger.add(
    sys.stdout,
    level="DEBUG" if settings.DEBUG else "INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)
logger.add(
    "/data/logs/smileygpt.log",
    rotation="10 MB",
    retention="14 days",
    level="INFO",
    enqueue=True,
    backtrace=False,
    diagnose=False,
)


def get_logger(name: str):
    return logger.bind(module=name)
