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


def get_send_logs(limit: int = 100) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute("SELECT * FROM send_logs ORDER BY id DESC LIMIT ?", (min(max(limit, 1), 500),)).fetchall()
    return [dict(row) for row in rows]


def latest_upload() -> str:
    with connection() as conn:
        row = conn.execute("SELECT MAX(uploaded_at) AS uploaded_at FROM visit_records").fetchone()
    return row["uploaded_at"] or ""
