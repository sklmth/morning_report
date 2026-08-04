"""
天命赦令 - 数据库模块
管理休假记录、抽签历史、月度统计
"""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional
from pathlib import Path

# 使用与主系统相同的数据库
DB_PATH = Path(__file__).parent.parent / "data" / "fill_records.db"


def get_connection() -> sqlite3.Connection:
    """获取数据库连接。"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_tables():
    """初始化天命赦令相关表。"""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. 休假记录表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vacation_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manager_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            note TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vacation_dates ON vacation_records(start_date, end_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vacation_manager ON vacation_records(manager_name)")

    # 2. 抽签历史表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lottery_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manager_name TEXT NOT NULL,
            consumed_ontime_count INTEGER NOT NULL,
            prize_name TEXT NOT NULL,
            prize_amount INTEGER NOT NULL,
            month TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lottery_month ON lottery_history(month)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lottery_manager ON lottery_history(manager_name)")

    # 3. 月度统计缓存表（存储每人每月的准时次数、已抽签次数、奖品总额）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monthly_lottery_stats (
            manager_name TEXT NOT NULL,
            month TEXT NOT NULL,
            ontime_count INTEGER NOT NULL DEFAULT 0,
            used_ontime_count INTEGER NOT NULL DEFAULT 0,
            total_prize_amount INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (manager_name, month)
        )
    """)

    conn.commit()
    conn.close()


def add_vacation(manager_name: str, start_date: str, end_date: str, note: str = "") -> int:
    """添加休假记录。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO vacation_records (manager_name, start_date, end_date, note) VALUES (?, ?, ?, ?)",
        (manager_name, start_date, end_date, note),
    )
    conn.commit()
    vacation_id = cursor.lastrowid
    conn.close()
    return vacation_id


def get_vacations(manager_name: Optional[str] = None) -> list[dict[str, Any]]:
    """获取休假记录列表。"""
    conn = get_connection()
    cursor = conn.cursor()
    if manager_name:
        cursor.execute(
            "SELECT * FROM vacation_records WHERE manager_name = ? ORDER BY start_date DESC",
            (manager_name,),
        )
    else:
        cursor.execute("SELECT * FROM vacation_records ORDER BY start_date DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_vacation(vacation_id: int) -> bool:
    """删除休假记录。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vacation_records WHERE id = ?", (vacation_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def is_on_vacation(manager_name: str, check_date: str) -> bool:
    """检查指定日期是否在休假期间（包括休假前一天）。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 1 FROM vacation_records
        WHERE manager_name = ?
          AND date(?) BETWEEN date(start_date, '-1 day') AND date(end_date)
        LIMIT 1
        """,
        (manager_name, check_date),
    )
    result = cursor.fetchone()
    conn.close()
    return result is not None


def add_lottery_record(
    manager_name: str, consumed_ontime_count: int, prize_name: str, prize_amount: int, month: str
) -> int:
    """记录一次抽签。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO lottery_history (manager_name, consumed_ontime_count, prize_name, prize_amount, month)
        VALUES (?, ?, ?, ?, ?)
        """,
        (manager_name, consumed_ontime_count, prize_name, prize_amount, month),
    )
    conn.commit()
    lottery_id = cursor.lastrowid
    conn.close()
    return lottery_id


def get_lottery_history(manager_name: Optional[str] = None, month: Optional[str] = None) -> list[dict[str, Any]]:
    """获取抽签历史。"""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM lottery_history WHERE 1=1"
    params = []

    if manager_name:
        query += " AND manager_name = ?"
        params.append(manager_name)

    if month:
        query += " AND month = ?"
        params.append(month)

    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_monthly_stats(manager_name: str, month: str) -> dict[str, Any]:
    """获取指定客户经理的月度统计。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM monthly_lottery_stats WHERE manager_name = ? AND month = ?",
        (manager_name, month),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    else:
        return {
            "manager_name": manager_name,
            "month": month,
            "ontime_count": 0,
            "used_ontime_count": 0,
            "total_prize_amount": 0,
        }


def update_monthly_stats(manager_name: str, month: str, ontime_count: int):
    """更新月度准时次数统计。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO monthly_lottery_stats (manager_name, month, ontime_count, used_ontime_count, total_prize_amount)
        VALUES (?, ?, ?, 0, 0)
        ON CONFLICT(manager_name, month) DO UPDATE SET ontime_count = ?
        """,
        (manager_name, month, ontime_count, ontime_count),
    )
    conn.commit()
    conn.close()


def consume_ontime_and_add_prize(manager_name: str, month: str, consumed_count: int, prize_amount: int):
    """消耗准时次数并增加奖品总额。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE monthly_lottery_stats
        SET used_ontime_count = used_ontime_count + ?,
            total_prize_amount = total_prize_amount + ?
        WHERE manager_name = ? AND month = ?
        """,
        (consumed_count, prize_amount, manager_name, month),
    )
    conn.commit()
    conn.close()


def get_all_managers_stats(month: str) -> list[dict[str, Any]]:
    """获取所有客户经理的月度统计（包含可用抽签次数）。"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            manager_name,
            month,
            ontime_count,
            used_ontime_count,
            total_prize_amount,
            (ontime_count - used_ontime_count) / 3 as available_lottery_count
        FROM monthly_lottery_stats
        WHERE month = ?
        ORDER BY ontime_count DESC
        """,
        (month,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
