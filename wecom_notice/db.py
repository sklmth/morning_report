import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from wecom_notice.config import DB_PATH, DEFAULT_RULES

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS visit_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_record_id TEXT UNIQUE,
    payload_hash TEXT NOT NULL UNIQUE,
    uploaded_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    manager_name TEXT,
    object_type TEXT,
    company_name TEXT,
    contact_name_title TEXT,
    contact_mobile TEXT,
    appointment_date TEXT,
    appointment_slot TEXT,
    need_dispatch TEXT,
    delivery_staff_name TEXT,
    opportunity_type TEXT,
    opportunity_type_extra TEXT,
    opportunity_content TEXT,
    cockpit_sent TEXT,
    doubao_beik_sent TEXT,
    visit_result TEXT,
    actual_visit_date TEXT,
    visit_situation TEXT,
    images_json TEXT,
    conversion_status TEXT,
    opportunity_points REAL NOT NULL DEFAULT 0,
    gaotao_count REAL NOT NULL DEFAULT 0,
    planned_accept_time TEXT,
    reschedule_time TEXT,
    reschedule_reason TEXT,
    raw_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_visit_records_appointment ON visit_records(appointment_date, manager_name);
CREATE INDEX IF NOT EXISTS idx_visit_records_uploaded_at ON visit_records(uploaded_at);

CREATE TABLE IF NOT EXISTS notification_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    trigger_type TEXT NOT NULL DEFAULT 'manual',
    cron_expr TEXT NOT NULL DEFAULT '',
    filter_json TEXT NOT NULL DEFAULT '{}',
    recipient_policy_json TEXT NOT NULL DEFAULT '{}',
    template_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS send_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_key TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    status TEXT NOT NULL,
    message_text TEXT NOT NULL,
    mentioned_json TEXT NOT NULL DEFAULT '[]',
    record_ids_json TEXT NOT NULL DEFAULT '[]',
    webhook_response TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_send_logs_sent_at ON send_logs(sent_at);

CREATE TABLE IF NOT EXISTS fill_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    manager_name TEXT NOT NULL,
    fill_status TEXT NOT NULL,
    fill_time TEXT,
    fill_count INTEGER DEFAULT 0,
    reminder_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(date, manager_name)
);
CREATE INDEX IF NOT EXISTS idx_fill_stats_date ON fill_statistics(date);
CREATE INDEX IF NOT EXISTS idx_fill_stats_status ON fill_statistics(fill_status);

CREATE TABLE IF NOT EXISTS reminder_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    manager_name TEXT NOT NULL,
    reminded_at TEXT NOT NULL,
    current_count INTEGER DEFAULT 0,
    reminder_sequence INTEGER DEFAULT 1,
    overtime_count INTEGER DEFAULT 0,
    missing_count INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_reminder_logs_date ON reminder_logs(date, manager_name);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
"""

RECORD_COLUMNS = [
    "source_record_id", "payload_hash", "manager_name", "object_type", "company_name",
    "contact_name_title", "contact_mobile", "appointment_date", "appointment_slot",
    "need_dispatch", "delivery_staff_name", "opportunity_type", "opportunity_type_extra",
    "opportunity_content", "cockpit_sent", "doubao_beik_sent", "visit_result",
    "actual_visit_date", "visit_situation", "images_json", "conversion_status",
    "opportunity_points", "gaotao_count", "planned_accept_time", "reschedule_time",
    "reschedule_reason", "raw_json",
]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connection() as conn:
        conn.executescript(SCHEMA_SQL)
        timestamp = now()
        for rule in DEFAULT_RULES:
            conn.execute(
                """INSERT OR IGNORE INTO notification_rules
                   (rule_key, name, enabled, trigger_type, cron_expr, filter_json,
                    recipient_policy_json, template_key, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rule["key"], rule["name"], int(rule["enabled"]), rule["trigger_type"],
                    rule["cron_expr"], json.dumps(rule["filter"], ensure_ascii=False),
                    json.dumps(rule["recipient_policy"], ensure_ascii=False),
                    rule["template_key"], timestamp, timestamp,
                ),
            )
            # 上面是 INSERT OR IGNORE，已存在的行不会更新。收件人范围属于配置而非
            # 用户数据（前端不可编辑），所以每次启动都以 config.py 为准同步回来，
            # 否则改了 DEFAULT_RULES 对已部署的库不生效。
            conn.execute(
                "UPDATE notification_rules SET recipient_policy_json = ?, updated_at = ? "
                "WHERE rule_key = ? AND recipient_policy_json != ?",
                (
                    json.dumps(rule["recipient_policy"], ensure_ascii=False), timestamp,
                    rule["key"], json.dumps(rule["recipient_policy"], ensure_ascii=False),
                ),
            )


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_records(records: list[dict[str, Any]]) -> dict[str, int]:
    inserted = 0
    updated = 0
    skipped = 0
    timestamp = now()
    placeholders = ", ".join("?" for _ in RECORD_COLUMNS)
    assignments = ", ".join(f"{column}=excluded.{column}" for column in RECORD_COLUMNS if column not in {"source_record_id", "payload_hash"})
    sql = f"""INSERT INTO visit_records ({", ".join(RECORD_COLUMNS)}, uploaded_at, updated_at)
              VALUES ({placeholders}, ?, ?)
              ON CONFLICT(source_record_id) DO UPDATE SET {assignments}, updated_at=excluded.updated_at"""
    with connection() as conn:
        for record in records:
            if not record["manager_name"] and not record["appointment_date"] and not record["company_name"]:
                skipped += 1
                continue
            existing = conn.execute(
                "SELECT id, payload_hash FROM visit_records WHERE source_record_id = ? OR payload_hash = ?",
                (record["source_record_id"] or None, record["payload_hash"]),
            ).fetchone()
            if existing and existing["payload_hash"] == record["payload_hash"]:
                skipped += 1
                continue
            values = [record[column] for column in RECORD_COLUMNS] + [timestamp, timestamp]
            try:
                conn.execute(sql, values)
            except sqlite3.IntegrityError:
                conn.execute(
                    "UPDATE visit_records SET updated_at = ? WHERE payload_hash = ?",
                    (timestamp, record["payload_hash"]),
                )
                skipped += 1
                continue
            if existing:
                updated += 1
            else:
                inserted += 1
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


def get_records(appointment_date: str = "", manager: str = "", status: str = "", limit: int = 300) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []
    if appointment_date:
        clauses.append("appointment_date = ?")
        params.append(appointment_date)
    if manager:
        clauses.append("manager_name = ?")
        params.append(manager)
    if status == "missing_result":
        clauses.append("(visit_result = '' OR visit_situation = '')")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(min(max(limit, 1), 500))
    with connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM visit_records {where} ORDER BY appointment_date DESC, manager_name, id DESC LIMIT ?", params
        ).fetchall()
    return [dict(row) for row in rows]


def get_records_by_date_range(start_date: str = "", end_date: str = "", manager: str = "") -> list[dict[str, Any]]:
    """按预约日期范围查询预约记录，用于累计统计和周五跨周末窗口统计。"""
    clauses = []
    params: list[Any] = []
    if start_date:
        clauses.append("appointment_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("appointment_date <= ?")
        params.append(end_date)
    if manager:
        clauses.append("manager_name = ?")
        params.append(manager)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM visit_records {where} ORDER BY appointment_date, manager_name, id",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def get_rules() -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute("SELECT * FROM notification_rules ORDER BY id").fetchall()
    result = []
    for row in rows:
        data = dict(row)
        data["enabled"] = bool(data["enabled"])
        data["filter"] = json.loads(data.pop("filter_json"))
        data["recipient_policy"] = json.loads(data.pop("recipient_policy_json"))
        result.append(data)
    return result


def get_rule(rule_key: str) -> dict[str, Any] | None:
    return next((rule for rule in get_rules() if rule["rule_key"] == rule_key), None)


def save_rule(rule_key: str, values: dict[str, Any]) -> dict[str, Any]:
    existing = get_rule(rule_key)
    if not existing:
        raise ValueError("规则不存在")
    merged = {**existing, **values}
    with connection() as conn:
        conn.execute(
            """UPDATE notification_rules SET name=?, enabled=?, trigger_type=?, cron_expr=?,
               filter_json=?, recipient_policy_json=?, template_key=?, updated_at=? WHERE rule_key=?""",
            (
                merged["name"], int(bool(merged["enabled"])), merged["trigger_type"], merged.get("cron_expr", ""),
                json.dumps(merged.get("filter", {}), ensure_ascii=False),
                json.dumps(merged.get("recipient_policy", {}), ensure_ascii=False),
                merged["template_key"], now(), rule_key,
            ),
        )
    return get_rule(rule_key) or merged


def add_send_log(rule_key: str, status: str, message_text: str, mentioned: list[dict[str, str]], record_ids: list[int], webhook_response: str = "", error: str = "") -> None:
    with connection() as conn:
        conn.execute(
            """INSERT INTO send_logs (rule_key, sent_at, status, message_text, mentioned_json,
               record_ids_json, webhook_response, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (rule_key, now(), status, message_text, json.dumps(mentioned, ensure_ascii=False),
             json.dumps(record_ids), webhook_response, error),
        )


def get_send_logs(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """按时间倒序取一页发送日志。offset 为跳过条数，用于前端翻页。"""
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM send_logs ORDER BY id DESC LIMIT ? OFFSET ?",
            (min(max(limit, 1), 500), max(offset, 0)),
        ).fetchall()
    result = []
    for row in rows:
        data = dict(row)
        data["mentioned"] = json.loads(data.pop("mentioned_json", "[]") or "[]")
        data["record_ids"] = json.loads(data.pop("record_ids_json", "[]") or "[]")
        result.append(data)
    return result


def count_send_logs() -> dict[str, int]:
    """全量日志的条数与成败分布。翻页后汇总数字仍按全量统计，不受当前页影响。"""
    with connection() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success,
                      SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
               FROM send_logs"""
        ).fetchone()
    return {
        "total": row["total"] or 0,
        "success_count": row["success"] or 0,
        "failed_count": row["failed"] or 0,
    }


def latest_upload() -> str:
    with connection() as conn:
        row = conn.execute("SELECT MAX(uploaded_at) AS uploaded_at FROM visit_records").fetchone()
    return row["uploaded_at"] or ""


# ====== 填报统计相关函数 ======


def upsert_fill_statistics(date: str, manager_name: str, fill_status: str, fill_time: str = "", fill_count: int = 0) -> None:
    """更新或插入填报统计记录。"""
    timestamp = now()
    with connection() as conn:
        conn.execute(
            """INSERT INTO fill_statistics (date, manager_name, fill_status, fill_time, fill_count, reminder_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 0, ?, ?)
               ON CONFLICT(date, manager_name) DO UPDATE SET
                   fill_status=excluded.fill_status,
                   fill_time=excluded.fill_time,
                   fill_count=excluded.fill_count,
                   updated_at=excluded.updated_at""",
            (date, manager_name, fill_status, fill_time, fill_count, timestamp, timestamp),
        )


def get_fill_statistics(start_date: str = "", end_date: str = "", manager: str = "", fill_status: str = "") -> list[dict[str, Any]]:
    """查询填报统计记录。"""
    clauses = []
    params: list[Any] = []
    if start_date:
        clauses.append("date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("date <= ?")
        params.append(end_date)
    if manager:
        clauses.append("manager_name = ?")
        params.append(manager)
    if fill_status:
        clauses.append("fill_status = ?")
        params.append(fill_status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connection() as conn:
        rows = conn.execute(f"SELECT * FROM fill_statistics {where} ORDER BY date DESC, manager_name", params).fetchall()
    return [dict(row) for row in rows]


def add_reminder_log(date: str, manager_name: str, current_count: int, reminder_sequence: int, overtime_count: int = 0, missing_count: int = 0) -> None:
    """记录提醒日志。"""
    with connection() as conn:
        conn.execute(
            """INSERT INTO reminder_logs (date, manager_name, reminded_at, current_count, reminder_sequence, overtime_count, missing_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (date, manager_name, now(), current_count, reminder_sequence, overtime_count, missing_count),
        )


def get_reminder_logs(date: str = "", manager: str = "", limit: int = 100) -> list[dict[str, Any]]:
    """查询提醒日志。"""
    clauses = []
    params: list[Any] = []
    if date:
        clauses.append("date = ?")
        params.append(date)
    if manager:
        clauses.append("manager_name = ?")
        params.append(manager)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(min(max(limit, 1), 500))
    with connection() as conn:
        rows = conn.execute(f"SELECT * FROM reminder_logs {where} ORDER BY reminded_at DESC LIMIT ?", params).fetchall()
    return [dict(row) for row in rows]


def get_manager_history_counts(manager_name: str, before_date: str = "") -> dict[str, int]:
    """获取客户经理本月累计的历史超时和漏填次数。"""
    from datetime import date as dt_date

    # 计算本月第一天
    today = dt_date.fromisoformat(before_date) if before_date else dt_date.today()
    month_start = today.replace(day=1).isoformat()

    # 2026-08-04 是本次系统启用日，整天按准时处理；8月从 08-05 起算。
    # 这个临时基线只影响 2026 年 8 月，进入下月后恢复按自然月第一天统计。
    statistics_start = "2026-08-05" if month_start == "2026-08-01" else month_start
    clauses = ["manager_name = ?", "date >= ?"]
    params: list[Any] = [manager_name, statistics_start]
    if before_date:
        clauses.append("date < ?")
        params.append(before_date)
    where = " AND ".join(clauses)
    with connection() as conn:
        overtime = conn.execute(
            f"SELECT COUNT(*) as cnt FROM fill_statistics WHERE {where} AND fill_status = 'overtime'", params
        ).fetchone()["cnt"]
        missing = conn.execute(
            f"SELECT COUNT(*) as cnt FROM fill_statistics WHERE {where} AND fill_status = 'missing'", params
        ).fetchone()["cnt"]
    return {"overtime_count": overtime, "missing_count": missing}


def increment_reminder_count(date: str, manager_name: str) -> int:
    """增加提醒次数，返回新的提醒次数。"""
    timestamp = now()
    with connection() as conn:
        # 先尝试获取现有记录
        existing = conn.execute(
            "SELECT id, reminder_count FROM fill_statistics WHERE date = ? AND manager_name = ?",
            (date, manager_name),
        ).fetchone()

        if existing:
            new_count = existing["reminder_count"] + 1
            conn.execute(
                "UPDATE fill_statistics SET reminder_count = ?, updated_at = ? WHERE id = ?",
                (new_count, timestamp, existing["id"]),
            )
            return new_count
        else:
            # 如果不存在，创建新记录（状态为pending）
            conn.execute(
                """INSERT INTO fill_statistics (date, manager_name, fill_status, fill_count, reminder_count, created_at, updated_at)
                   VALUES (?, ?, 'pending', 0, 1, ?, ?)""",
                (date, manager_name, timestamp, timestamp),
            )
            return 1


# ====== 应用设置 ======


def get_setting(key: str, default: str = "") -> str:
    """读取应用设置，key不存在时返回default。"""
    with connection() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def save_setting(key: str, value: str) -> None:
    """保存或更新应用设置。"""
    timestamp = now()
    with connection() as conn:
        conn.execute(
            """INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value, timestamp),
        )
