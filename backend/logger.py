"""统一日志系统 — 控制台 + 文件双输出，按模块分级.

用法：
    from backend.logger import logger
    logger.info("正在获取数据...")
    logger.warning("接口限流")
    logger.error("请求失败", exc_info=True)
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# ── 日志级别（可通过环境变量 FINANCEBOT_LOG_LEVEL 覆盖） ──
LOG_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
}

_LOG_LEVEL_NAME = os.getenv("FINANCEBOT_LOG_LEVEL", "info").lower()
LOG_LEVEL = LOG_LEVEL_MAP.get(_LOG_LEVEL_NAME, logging.INFO)

# ── 日志格式 ──
_CONSOLE_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_FILE_FMT = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
_DATE_FMT = "%H:%M:%S"


def setup_logging(
    log_dir: str = "",
    log_file: str = "",
    level: int = LOG_LEVEL,
    console: bool = True,
) -> logging.Logger:
    """初始化全局日志系统.

    Args:
        log_dir: 日志目录，默认 data/logs。
        log_file: 日志文件名，默认 financebot_YYYYMMDD.log。
        level: 日志级别。
        console: 是否同时输出到控制台。

    Returns:
        根日志器。
    """
    root = logging.getLogger("finance_bot")
    root.setLevel(level)

    # 清除已有 handler（防止重复添加）
    root.handlers.clear()

    # 控制台输出
    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(logging.Formatter(_CONSOLE_FMT, _DATE_FMT))
        root.addHandler(ch)

    # 文件输出
    if not log_dir:
        log_dir = str(Path(__file__).resolve().parent.parent / "data" / "logs")
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    if not log_file:
        log_file = f"financebot_{datetime.now():%Y%m%d}.log"
    fh = logging.FileHandler(
        Path(log_dir) / log_file,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(_FILE_FMT))
    root.addHandler(fh)

    # 降低第三方库的日志噪音
    for noisy in ("httpx", "urllib3", "sentence_transformers", "transformers",
                   "pymilvus", "akshare", "jieba", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return root


# ── 模块级便捷用法：from backend.logger import logger ──
logger = logging.getLogger("finance_bot")

# 首次导入时自动初始化
setup_logging()
