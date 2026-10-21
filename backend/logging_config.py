"""分级日志系统：控制台 + 滚动文件，支持按任务 ID 追踪排查。

用法：
    from logging_config import get_logger
    logger = get_logger("tasks")
    logger.info("[task:%s] 任务开始生成", task_id)
"""
import logging
from logging.handlers import RotatingFileHandler

from config import LOG_DIR

_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """初始化根日志器（幂等，重复调用不会重复添加 handler）。"""
    root = logging.getLogger()
    if root.handlers:
        return root

    root.setLevel(level)

    # 控制台输出
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(console)

    # 滚动文件（单文件 5MB，保留 5 份）
    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(file_handler)

    return root


def get_logger(name: str) -> logging.Logger:
    """获取命名日志器，自动挂载应用根配置。"""
    setup_logging()
    return logging.getLogger(name)
