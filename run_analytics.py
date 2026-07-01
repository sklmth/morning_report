"""
经营分析服务入口
同时启动：
  - FastAPI 服务 (端口 8992，由 nginx:8991 代理)
  - ReportWatcher 后台线程（监听8990的 morning_report.db，自动触发分析）
用法：
  python run_analytics.py
  # 或指定端口/DB路径：
  ANALYTICS_PORT=8992 ANALYTICS_DB_PATH=runtime/analytics.db python run_analytics.py
"""

import os
import sys

# 确保项目根目录在 Python 路径中
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from analytics.logging_setup import setup_logging

# 统一日志：控制台 + 压缩轮转文件（runtime/logs/analytics.log）
logger = setup_logging()


def main():
    import uvicorn
    from analytics.db import init_db
    from analytics.watcher import ReportWatcher

    # 初始化数据库
    init_db()
    logger.info("Analytics DB ready: %s",
                os.environ.get("ANALYTICS_DB_PATH", "runtime/analytics.db"))

    # 启动 watcher 后台线程
    watcher_interval = int(os.environ.get("WATCHER_INTERVAL", "30"))
    watcher = ReportWatcher(interval=watcher_interval)
    watcher.start()
    logger.info("ReportWatcher started (interval=%ds)", watcher_interval)

    # 启动 FastAPI 服务
    host = os.environ.get("ANALYTICS_HOST", "127.0.0.1")
    port = int(os.environ.get("ANALYTICS_PORT", "8992"))
    logger.info("Starting analytics API on %s:%d", host, port)
    logger.info("Frontend should be served by nginx on port 8991")
    logger.info("Nginx config: nginx/analytics.conf")

    uvicorn.run(
        "analytics.api.server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
        access_log=True,
        # log_config=None：不让 uvicorn 安装自己的 handler，
        # 其 logger 向上传播到 root，统一走文件+压缩轮转
        log_config=None,
    )


if __name__ == "__main__":
    main()
