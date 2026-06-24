"""
SQLite 存储层：保存每次早会数据处理结果，供网页回显。
"""

import json
import os
import sqlite3
from datetime import datetime


SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    subject TEXT,
    sender TEXT,
    status TEXT NOT NULL,
    message TEXT,
    input_files TEXT NOT NULL,
    output_xlsx TEXT,
    image_dir TEXT,
    images TEXT NOT NULL,
    report_text TEXT,
    written_sheets TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at DESC);
"""


class ReportStore:
    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()

    def init_db(self):
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def add_report(self, *, source, status, subject="", sender="", message="",
                   input_files=None, output_xlsx="", image_dir="", images=None,
                   report_text="", written_sheets=None, created_at=None):
        created_at = created_at or datetime.now().isoformat(timespec="seconds")
        input_files = input_files or []
        images = images or []
        written_sheets = written_sheets or []
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO reports (
                    created_at, source, subject, sender, status, message,
                    input_files, output_xlsx, image_dir, images, report_text,
                    written_sheets
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    source,
                    subject,
                    sender,
                    status,
                    message,
                    json.dumps(input_files, ensure_ascii=False),
                    output_xlsx,
                    image_dir,
                    json.dumps(images, ensure_ascii=False),
                    report_text,
                    json.dumps(written_sheets, ensure_ascii=False),
                ),
            )
            return cur.lastrowid

    def count_reports(self):
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]

    def list_reports(self, limit=50, offset=0):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reports ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (int(limit), int(offset)),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_report(self, report_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reports WHERE id = ?",
                (int(report_id),),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def latest_report(self):
        reports = self.list_reports(limit=1)
        return reports[0] if reports else None

    @staticmethod
    def _row_to_dict(row):
        item = dict(row)
        for key in ("input_files", "images", "written_sheets"):
            try:
                item[key] = json.loads(item.get(key) or "[]")
            except json.JSONDecodeError:
                item[key] = []
        return item
