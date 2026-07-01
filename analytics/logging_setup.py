"""
统一日志模块

特性：
  - 同时输出到控制台 + 文件（runtime/logs/analytics.log）
  - 每天午夜自动轮转，旧日志文件自动 gzip 压缩（节省磁盘）
  - 只保留最近 N 天（默认 14 天），更旧的归档自动删除，不会爆盘
  - 幂等：多次调用只初始化一次

环境变量（均可选）：
  ANALYTICS_LOG_DIR       日志目录，默认 <项目根>/runtime/logs
  ANALYTICS_LOG_LEVEL     日志级别，默认 INFO
  ANALYTICS_LOG_KEEP_DAYS 日志保留天数，默认 14（超过自动删除）
  ANALYTICS_LOG_CONSOLE   是否同时输出到控制台，默认 1（0 关闭）
"""

import gzip
import logging
import os
import shutil
from logging.handlers import TimedRotatingFileHandler

# 项目根目录（analytics/ 的上一级）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _gzip_namer(name: str) -> str:
    """归档统一带 .gz 后缀，父类删除超期归档时也按 .gz 名匹配"""
    return name + ".gz"


def _gzip_rotator(source: str, dest: str) -> None:
    """把轮转出的日志压成 .gz 并删除未压缩原文件；失败则退回普通重命名"""
    try:
        with open(source, "rb") as f_in, gzip.open(dest, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.remove(source)
    except OSError:
        # 压缩失败时至少保留一份未压缩归档，不丢日志
        if os.path.exists(source):
            fallback = dest[:-3] if dest.endswith(".gz") else dest
            try:
                os.replace(source, fallback)
            except OSError:
                pass


def _resolve_log_dir() -> str:
    env_dir = os.environ.get("ANALYTICS_LOG_DIR")
    if env_dir:
        return env_dir
    return os.path.join(_ROOT, "runtime", "logs")


def setup_logging(force: bool = False) -> logging.Logger:
    """
    初始化根 logger（控制台 + 按天轮转的压缩文件）。
    重复调用无副作用；返回 'analytics' logger。
    """
    global _configured
    root = logging.getLogger()
    if _configured and not force:
        return logging.getLogger("analytics")

    level_name = os.environ.get("ANALYTICS_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    keep_days = int(os.environ.get("ANALYTICS_LOG_KEEP_DAYS", "14"))
    to_console = os.environ.get("ANALYTICS_LOG_CONSOLE", "1") != "0"

    log_dir = _resolve_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "analytics.log")

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # 清掉已有 handler（避免 basicConfig 或重复调用导致重复输出）
    for h in list(root.handlers):
        root.removeHandler(h)

    # 每天午夜轮转：analytics.log -> analytics.log.2026-07-01.gz
    # backupCount=keep_days 表示只保留最近 keep_days 个（天），更旧的自动删除
    file_handler = TimedRotatingFileHandler(
        log_path,
        when="midnight",
        interval=1,
        backupCount=keep_days,
        encoding="utf-8",
        utc=False,
    )
    # 轮转钩子：归档统一以 .gz 命名并压缩，父类据此正确删除超期归档
    file_handler.namer = _gzip_namer
    file_handler.rotator = _gzip_rotator
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if to_console:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

    root.setLevel(level)

    _configured = True
    logger = logging.getLogger("analytics")
    logger.info(
        "Logging initialized: dir=%s level=%s keep_days=%d console=%s",
        log_dir, level_name, keep_days, to_console,
    )
    return logger
