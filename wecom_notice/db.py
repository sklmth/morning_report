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

-- 奖品钱包：记录每个客户经理获得的每一个奖品（来源：抽签/业绩）
CREATE TABLE IF NOT EXISTS prize_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manager_name TEXT NOT NULL,
    month TEXT NOT NULL,
    prize_name TEXT NOT NULL,
    face_amount INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'lottery',   -- 'lottery' | 'performance'
    source_ref_id INTEGER,                    -- lottery_history.id 或 dispatch.id
    acquired_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available', -- available | exhausted
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_prize_items_mgr ON prize_items(manager_name, month, status);

-- 罚款抵扣事件：记录奖品如何抵扣罚款
CREATE TABLE IF NOT EXISTS fine_coverage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manager_name TEXT NOT NULL,
    month TEXT NOT NULL,
    prize_item_id INTEGER REFERENCES prize_items(id),
    covered_amount INTEGER NOT NULL,
    total_fine_at_time INTEGER NOT NULL DEFAULT 0,
    covered_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);

-- 完美一单上传记录
CREATE TABLE IF NOT EXISTS performance_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    file_date TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);

-- 每次上传对应的客户经理累计统计
CREATE TABLE IF NOT EXISTS performance_manager_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_id INTEGER NOT NULL REFERENCES performance_uploads(id),
    month TEXT NOT NULL,
    manager_name TEXT NOT NULL,
    cumulative_points REAL NOT NULL DEFAULT 0,
    cumulative_gaotao REAL NOT NULL DEFAULT 0,
    UNIQUE(upload_id, manager_name)
);
CREATE INDEX IF NOT EXISTS idx_perf_stats_month ON performance_manager_stats(month, manager_name);

-- 业绩奖励下发配置（每轮可自定义排名和奖项）
CREATE TABLE IF NOT EXISTS performance_award_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    award_round INTEGER NOT NULL DEFAULT 1,
    rank_from INTEGER NOT NULL,
    rank_to INTEGER NOT NULL,
    metric TEXT NOT NULL DEFAULT 'points',   -- 'points' | 'gaotao'
    prize_name TEXT NOT NULL,
    prize_amount INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

-- 奖励下发记录
CREATE TABLE IF NOT EXISTS performance_award_dispatches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    award_round INTEGER NOT NULL DEFAULT 1,
    dispatch_date TEXT NOT NULL,
    manager_name TEXT NOT NULL,
    prize_name TEXT NOT NULL,
    prize_amount INTEGER NOT NULL,
    metric TEXT NOT NULL DEFAULT 'points',
    rank_position INTEGER NOT NULL DEFAULT 0,
    is_revoked INTEGER NOT NULL DEFAULT 0,
    revoked_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_perf_dispatch_month ON performance_award_dispatches(month, manager_name);

-- 下发时历史快照（历史看板数据源）
CREATE TABLE IF NOT EXISTS performance_dispatch_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    award_round INTEGER NOT NULL,
    dispatch_date TEXT NOT NULL,
    manager_name TEXT NOT NULL,
    cumulative_points REAL NOT NULL DEFAULT 0,
    cumulative_gaotao REAL NOT NULL DEFAULT 0,
    inc_points REAL NOT NULL DEFAULT 0,
    inc_gaotao REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_perf_snapshot_month ON performance_dispatch_snapshots(month, award_round);
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


def mark_airscript_upload_received() -> str:
    """记录金山脚本最近一次成功上传时间，即使数据内容完全重复也更新。"""
    timestamp = now()
    save_setting("last_airscript_upload_at", timestamp)
    return timestamp


def latest_airscript_upload() -> str:
    return get_setting("last_airscript_upload_at", "")


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
    """获取客户经理本月累计的准时、超时和漏填次数。"""
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
        on_time = conn.execute(
            f"SELECT COUNT(*) as cnt FROM fill_statistics WHERE {where} AND fill_status = 'on_time'", params
        ).fetchone()["cnt"]
        overtime = conn.execute(
            f"SELECT COUNT(*) as cnt FROM fill_statistics WHERE {where} AND fill_status = 'overtime'", params
        ).fetchone()["cnt"]
        missing = conn.execute(
            f"SELECT COUNT(*) as cnt FROM fill_statistics WHERE {where} AND fill_status = 'missing'", params
        ).fetchone()["cnt"]
    return {"on_time_count": on_time, "overtime_count": overtime, "missing_count": missing}


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


# ====== 奖品钱包 ======

# 面值 → 奖品名映射（用于"找零"时生成新奖品名）
_AMOUNT_TO_PRIZE: dict[int, str] = {
    0: "凡尘符咒",
    5: "聚灵丹",
    10: "护身符",
    15: "筑基丹",
    20: "天罡令",
    25: "金丹圣果",
    30: "天命赦令",
}


def _prize_name_for_amount(amount: int) -> str:
    """根据金额返回最接近的奖品名（用于找零）。"""
    if amount in _AMOUNT_TO_PRIZE:
        return _AMOUNT_TO_PRIZE[amount]
    # 向下取整到最接近的
    for v in sorted(_AMOUNT_TO_PRIZE.keys(), reverse=True):
        if v <= amount:
            return _AMOUNT_TO_PRIZE[v]
    return "聚灵丹"


def add_prize_item(
    manager_name: str,
    month: str,
    prize_name: str,
    face_amount: int,
    source: str,
    source_ref_id: int | None = None,
    note: str = "",
) -> int:
    """入库一个新奖品。返回 prize_item id。"""
    if face_amount <= 0:
        return -1  # 空奖不入库
    timestamp = now()
    with connection() as conn:
        cursor = conn.execute(
            """INSERT INTO prize_items
               (manager_name, month, prize_name, face_amount, source, source_ref_id, acquired_at, status, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'available', ?)""",
            (manager_name, month, prize_name, face_amount, source, source_ref_id, timestamp, note),
        )
        return cursor.lastrowid


def get_prize_items(manager_name: str, month: str, status: str = "") -> list[dict[str, Any]]:
    """获取奖品列表。status 为空时返回所有。"""
    clauses = ["manager_name = ?", "month = ?"]
    params: list[Any] = [manager_name, month]
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = " AND ".join(clauses)
    with connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM prize_items WHERE {where} ORDER BY acquired_at",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_prize_items_month(month: str) -> list[dict[str, Any]]:
    """获取指定月份所有客户经理的奖品。"""
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM prize_items WHERE month = ? ORDER BY manager_name, acquired_at",
            (month,),
        ).fetchall()
    return [dict(r) for r in rows]


def apply_prize_against_fine(
    manager_name: str,
    month: str,
    prize_item_id: int,
    total_fine: int,
) -> dict[str, Any]:
    """
    用指定奖品抵扣罚款。处理找零逻辑。

    返回：
      {
        "covered": int,         # 本次实际抵扣金额
        "change_item_id": int,  # 找零产生的新奖品 id（-1 表示没有找零）
        "change_amount": int,   # 找零金额
      }
    """
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM prize_items WHERE id = ? AND manager_name = ? AND status = 'available'",
            (prize_item_id, manager_name),
        ).fetchone()
    if not row:
        return {"covered": 0, "change_item_id": -1, "change_amount": 0}

    prize = dict(row)
    face = prize["face_amount"]

    # 当前已抵扣总额（用于计算实际欠款）
    already_covered = get_total_prize_covered(manager_name, month)
    outstanding = max(0, total_fine - already_covered)

    if outstanding <= 0:
        return {"covered": 0, "change_item_id": -1, "change_amount": 0}

    covered = min(face, outstanding)
    change_amount = face - covered  # 找零

    timestamp = now()
    with connection() as conn:
        # 标记奖品已用尽
        conn.execute(
            "UPDATE prize_items SET status = 'exhausted' WHERE id = ?",
            (prize_item_id,),
        )
        # 记录抵扣事件
        conn.execute(
            """INSERT INTO fine_coverage_events
               (manager_name, month, prize_item_id, covered_amount, total_fine_at_time, covered_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (manager_name, month, prize_item_id, covered, total_fine, timestamp),
        )

    # 处理找零：生成新奖品入库
    change_id = -1
    if change_amount > 0:
        change_name = _prize_name_for_amount(change_amount)
        change_id = add_prize_item(
            manager_name, month, change_name, change_amount,
            source=prize["source"],
            source_ref_id=prize["id"],
            note=f"找零：{prize['prize_name']}({face}元)→{covered}元，余{change_amount}元",
        )

    return {"covered": covered, "change_item_id": change_id, "change_amount": change_amount}


def auto_apply_prizes(manager_name: str, month: str, total_fine: int) -> dict[str, Any]:
    """
    自动将所有 available 奖品按顺序抵扣罚款。

    返回：
      {"total_covered": int, "events": [...]}
    """
    available = [p for p in get_prize_items(manager_name, month, status="available")]
    total_covered = get_total_prize_covered(manager_name, month)

    events = []
    for prize in available:
        outstanding = max(0, total_fine - total_covered)
        if outstanding <= 0:
            break
        result = apply_prize_against_fine(manager_name, month, prize["id"], total_fine)
        if result["covered"] > 0:
            total_covered += result["covered"]
            events.append({
                "prize_id": prize["id"],
                "prize_name": prize["prize_name"],
                "covered": result["covered"],
                "change_amount": result["change_amount"],
            })
        # 如果找零产生新奖品，下一轮自然会处理（因为已入库 available）
    return {"total_covered": total_covered, "events": events}


def get_total_prize_covered(manager_name: str, month: str) -> int:
    """获取本月已抵扣罚款总额。"""
    with connection() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(covered_amount), 0) AS total
               FROM fine_coverage_events
               WHERE manager_name = ? AND month = ?""",
            (manager_name, month),
        ).fetchone()
    return int(row["total"])


def get_available_prize_total(manager_name: str, month: str) -> int:
    """获取尚未使用的奖品总面值（available 状态）。"""
    with connection() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(face_amount), 0) AS total
               FROM prize_items
               WHERE manager_name = ? AND month = ? AND status = 'available'""",
            (manager_name, month),
        ).fetchone()
    return int(row["total"])


# ====== 业绩奖励 ======


def save_performance_upload(month: str, file_date: str, note: str = "") -> int:
    """记录一次完美一单上传。返回 upload_id。"""
    timestamp = now()
    with connection() as conn:
        cursor = conn.execute(
            "INSERT INTO performance_uploads (month, file_date, uploaded_at, note) VALUES (?, ?, ?, ?)",
            (month, file_date, timestamp, note),
        )
        return cursor.lastrowid


def save_performance_stats(upload_id: int, month: str, stats: list[dict[str, Any]]) -> None:
    """保存客户经理业绩统计（upsert）。stats 每项含 manager_name, cumulative_points, cumulative_gaotao。"""
    with connection() as conn:
        for s in stats:
            conn.execute(
                """INSERT INTO performance_manager_stats
                   (upload_id, month, manager_name, cumulative_points, cumulative_gaotao)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(upload_id, manager_name) DO UPDATE SET
                       cumulative_points = excluded.cumulative_points,
                       cumulative_gaotao = excluded.cumulative_gaotao""",
                (upload_id, month, s["manager_name"], s["cumulative_points"], s["cumulative_gaotao"]),
            )


def get_performance_uploads(month: str) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM performance_uploads WHERE month = ? ORDER BY uploaded_at DESC",
            (month,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_latest_performance_upload(month: str) -> dict[str, Any] | None:
    uploads = get_performance_uploads(month)
    return uploads[0] if uploads else None


def get_performance_stats(month: str, upload_id: int | None = None) -> list[dict[str, Any]]:
    """获取指定月份/upload_id 的业绩统计，默认取最新一次上传。"""
    if upload_id is None:
        latest = get_latest_performance_upload(month)
        if not latest:
            return []
        upload_id = latest["id"]
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM performance_manager_stats WHERE upload_id = ? ORDER BY cumulative_points DESC",
            (upload_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_award_config(
    month: str,
    award_round: int,
    rank_from: int,
    rank_to: int,
    metric: str,
    prize_name: str,
    prize_amount: int,
    note: str = "",
) -> int:
    timestamp = now()
    with connection() as conn:
        cursor = conn.execute(
            """INSERT INTO performance_award_configs
               (month, award_round, rank_from, rank_to, metric, prize_name, prize_amount, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (month, award_round, rank_from, rank_to, metric, prize_name, prize_amount, note, timestamp),
        )
        return cursor.lastrowid


def get_award_configs(month: str, award_round: int | None = None) -> list[dict[str, Any]]:
    clauses = ["month = ?"]
    params: list[Any] = [month]
    if award_round is not None:
        clauses.append("award_round = ?")
        params.append(award_round)
    where = " AND ".join(clauses)
    with connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM performance_award_configs WHERE {where} ORDER BY award_round, rank_from",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def delete_award_config(config_id: int) -> bool:
    with connection() as conn:
        conn.execute("DELETE FROM performance_award_configs WHERE id = ?", (config_id,))
    return True


def dispatch_awards(month: str, award_round: int, dispatch_date: str, dispatches: list[dict[str, Any]]) -> list[int]:
    """
    批量下发奖励入库，并自动触发奖品抵扣逻辑。
    dispatches 每项: {manager_name, prize_name, prize_amount, metric, rank_position, note}
    返回所有 dispatch_id 列表。
    """
    timestamp = now()
    ids = []
    with connection() as conn:
        for d in dispatches:
            cursor = conn.execute(
                """INSERT INTO performance_award_dispatches
                   (month, award_round, dispatch_date, manager_name, prize_name, prize_amount,
                    metric, rank_position, is_revoked, revoked_at, created_at, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, '', ?, ?)""",
                (
                    month, award_round, dispatch_date,
                    d["manager_name"], d["prize_name"], d["prize_amount"],
                    d.get("metric", "points"), d.get("rank_position", 0),
                    timestamp, d.get("note", ""),
                ),
            )
            dispatch_id = cursor.lastrowid
            ids.append(dispatch_id)

    # 每个奖品入库，然后立即自动抵扣
    from datetime import date as dt_date
    from wecom_notice.reporter import compute_fine_for_manager  # 延迟导入避免循环
    for d, dispatch_id in zip(dispatches, ids):
        mgr = d["manager_name"]
        amount = d["prize_amount"]
        if amount > 0:
            add_prize_item(mgr, month, d["prize_name"], amount, "performance", dispatch_id)
            # 计算当前罚款，自动抵扣
            try:
                total_fine = compute_fine_for_manager(mgr, month)
                if total_fine > 0:
                    auto_apply_prizes(mgr, month, total_fine)
            except Exception:
                pass

    return ids


def revoke_dispatch(dispatch_id: int) -> bool:
    """撤回一条奖励下发记录，并回收对应奖品项。"""
    timestamp = now()
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM performance_award_dispatches WHERE id = ? AND is_revoked = 0",
            (dispatch_id,),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE performance_award_dispatches SET is_revoked = 1, revoked_at = ? WHERE id = ?",
            (timestamp, dispatch_id),
        )
        # 将对应 prize_item 标记为 revoked（如果还是 available 状态）
        conn.execute(
            """UPDATE prize_items SET status = 'revoked', note = '已撤回'
               WHERE source = 'performance' AND source_ref_id = ? AND status = 'available'""",
            (dispatch_id,),
        )
    return True


def get_dispatches(month: str, include_revoked: bool = False) -> list[dict[str, Any]]:
    params: list[Any] = [month]
    extra = "" if include_revoked else " AND is_revoked = 0"
    with connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM performance_award_dispatches WHERE month = ?{extra} ORDER BY dispatch_date DESC, created_at DESC",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def save_performance_snapshot(
    month: str, award_round: int, dispatch_date: str, current_stats: list[dict[str, Any]]
) -> None:
    """
    在下发奖励时保存快照：记录所有客户经理此刻的累计数据，以及较上一轮快照的增量。
    current_stats 每项含 manager_name, cumulative_points, cumulative_gaotao。
    """
    # 取本月上一轮（award_round-1 及之前）最新那轮的快照，用于计算增量
    with connection() as conn:
        prev_rows = conn.execute(
            """SELECT * FROM performance_dispatch_snapshots
               WHERE month = ? AND award_round < ?
               ORDER BY award_round DESC""",
            (month, award_round),
        ).fetchall()

    prev_map: dict[str, dict[str, Any]] = {}
    if prev_rows:
        max_prev_round = prev_rows[0]["award_round"]
        for r in prev_rows:
            if r["award_round"] == max_prev_round:
                prev_map[r["manager_name"]] = dict(r)

    timestamp = now()
    with connection() as conn:
        # 如果同一轮已有快照，先删旧的（重复下发时覆盖）
        conn.execute(
            "DELETE FROM performance_dispatch_snapshots WHERE month = ? AND award_round = ?",
            (month, award_round),
        )
        for s in current_stats:
            name = s["manager_name"]
            prev = prev_map.get(name)
            inc_pts = s["cumulative_points"] - (prev["cumulative_points"] if prev else 0)
            inc_gt = s["cumulative_gaotao"] - (prev["cumulative_gaotao"] if prev else 0)
            conn.execute(
                """INSERT INTO performance_dispatch_snapshots
                   (month, award_round, dispatch_date, manager_name,
                    cumulative_points, cumulative_gaotao, inc_points, inc_gaotao, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    month, award_round, dispatch_date, name,
                    s["cumulative_points"], s["cumulative_gaotao"],
                    max(inc_pts, 0), max(inc_gt, 0),
                    timestamp,
                ),
            )


def get_performance_snapshots(month: str) -> list[dict[str, Any]]:
    """
    获取指定月份的所有历史快照，按轮次升序分组返回。
    每组结构：{award_round, dispatch_date, month, rows:[{manager_name, cumulative_points, ...}]}
    rows 内按累计积分降序排列。
    """
    with connection() as conn:
        rows = conn.execute(
            """SELECT * FROM performance_dispatch_snapshots
               WHERE month = ?
               ORDER BY award_round ASC, cumulative_points DESC""",
            (month,),
        ).fetchall()

    rows = [dict(r) for r in rows]
    groups: dict[tuple, dict[str, Any]] = {}
    for r in rows:
        key = (r["award_round"], r["dispatch_date"])
        if key not in groups:
            groups[key] = {
                "award_round": r["award_round"],
                "dispatch_date": r["dispatch_date"],
                "month": r["month"],
                "rows": [],
            }
        groups[key]["rows"].append(r)

    return sorted(groups.values(), key=lambda g: g["award_round"])


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
