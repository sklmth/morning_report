"""
8990 DB 监听器
后台线程轮询 morning_report.db，发现新的成功记录后自动触发分析数据入库
"""

import json
import logging
import os
import sqlite3
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# 8990 默认 DB 路径（与 storage.py 保持一致）
DEFAULT_REPORT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "runtime", "morning_report.db"
)

# 记录上次处理到的最大 id，持久化在 analytics.db 的 key-value 表中
_LAST_ID_KEY = "watcher_last_report_id"


def _get_last_processed_id(analytics_conn: sqlite3.Connection) -> int:
    analytics_conn.execute(
        "CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, value TEXT)"
    )
    row = analytics_conn.execute(
        "SELECT value FROM kv_store WHERE key=?", (_LAST_ID_KEY,)
    ).fetchone()
    return int(row["value"]) if row else 0


def _set_last_processed_id(analytics_conn: sqlite3.Connection, id_: int):
    analytics_conn.execute(
        "INSERT OR REPLACE INTO kv_store(key, value) VALUES (?, ?)",
        (_LAST_ID_KEY, str(id_))
    )
    analytics_conn.commit()


def _scan_new_reports(report_db_path: str, since_id: int) -> list[dict]:
    """从 8990 的 reports 表读取新的成功记录"""
    if not os.path.exists(report_db_path):
        return []
    try:
        conn = sqlite3.connect(report_db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, input_files FROM reports WHERE id > ? AND status='success' ORDER BY id ASC",
            (since_id,)
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            try:
                files = json.loads(r["input_files"]) if r["input_files"] else []
            except Exception:
                files = []
            result.append({"id": r["id"], "input_files": files})
        return result
    except Exception as e:
        logger.warning("watcher scan error: %s", e)
        return []


class ReportWatcher(threading.Thread):
    """
    后台监听线程
    每隔 interval 秒扫描一次 morning_report.db
    发现新记录时调用 pipeline.process_files_list 入库
    """
    def __init__(self, interval: int = 30,
                 report_db_path: Optional[str] = None,
                 analytics_db_path: Optional[str] = None):
        super().__init__(daemon=True, name="report-watcher")
        self.interval = interval
        self.report_db_path = report_db_path or os.environ.get("REPORT_DB_PATH", DEFAULT_REPORT_DB)
        self.analytics_db_path = analytics_db_path
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        # 延迟导入避免循环
        from analytics.db import get_connection
        from analytics.pipeline import process_files_list

        logger.info("ReportWatcher started, polling %s every %ds", self.report_db_path, self.interval)

        while not self._stop_event.is_set():
            try:
                analytics_conn = get_connection(self.analytics_db_path)
                last_id = _get_last_processed_id(analytics_conn)
                new_reports = _scan_new_reports(self.report_db_path, last_id)

                if new_reports:
                    logger.info("Watcher found %d new report(s)", len(new_reports))

                max_id = last_id
                for report in new_reports:
                    files = report["input_files"]
                    if files:
                        results = process_files_list(
                            files,
                            trigger_by="watch",
                            morning_report_id=report["id"],
                            db_path=self.analytics_db_path
                        )
                        for r in results:
                            logger.info("watcher processed: %s", r.get("msg", ""))
                    max_id = max(max_id, report["id"])

                if max_id > last_id:
                    _set_last_processed_id(analytics_conn, max_id)

                analytics_conn.close()

            except Exception as e:
                logger.exception("Watcher loop error: %s", e)

            self._stop_event.wait(self.interval)

        logger.info("ReportWatcher stopped")
