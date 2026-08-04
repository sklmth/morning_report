"""历史填报记录清零 —— 一次性运维脚本。

把起算日之前的 overtime / missing 记录标记为 on_time，使其不再计入
「本月记录」和下午茶基金金额。

注意：当 fill_statistics 为空时，部分汇总会从 visit_records 即时反推历史漏填。
如需让系统真正“从某天开始重新算”，请同时归档起算日前的 visit_records。

用法（先看效果，再执行）：
    python -m wecom_notice.reset_history --before 2026-08-04
    python -m wecom_notice.reset_history --before 2026-08-04 --archive-visits
    python -m wecom_notice.reset_history --before 2026-08-04 --archive-visits --apply

--apply 前会自动备份数据库到 runtime/backup/。
"""

import argparse
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path

from wecom_notice.config import DB_PATH


def backup_db() -> Path:
    backup_dir = Path(DB_PATH).parent / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"wecom_notice_{stamp}.db"
    shutil.copy2(DB_PATH, dest)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="清零起算日之前的漏填/超时记录")
    parser.add_argument("--before", default=date.today().isoformat(),
                        help="起算日（YYYY-MM-DD），该日期之前的记录全部视为过关。默认今天")
    parser.add_argument("--apply", action="store_true", help="真正写入；不加则只预览")
    parser.add_argument(
        "--archive-visits",
        action="store_true",
        help="同时归档并移出起算日前的 visit_records，避免从预约记录反推历史漏填",
    )
    args = parser.parse_args()

    try:
        cutoff = date.fromisoformat(args.before).isoformat()
    except ValueError:
        raise SystemExit(f"--before 日期格式错误：{args.before}")

    if not Path(DB_PATH).exists():
        raise SystemExit(f"数据库不存在：{DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """SELECT manager_name, fill_status, COUNT(*) AS cnt
           FROM fill_statistics
           WHERE date < ? AND fill_status IN ('overtime', 'missing')
           GROUP BY manager_name, fill_status
           ORDER BY manager_name, fill_status""",
        (cutoff,),
    ).fetchall()
    old_visit_count = conn.execute(
        "SELECT COUNT(*) FROM visit_records WHERE appointment_date < ?",
        (cutoff,),
    ).fetchone()[0]

    total = sum(row["cnt"] for row in rows)
    print(f"数据库：{DB_PATH}")
    print(f"起算日：{cutoff}（此日期之前的记录将视为历史过关）\n")

    if total:
        print(f"{'客户经理':<10}{'状态':<10}{'条数':>6}")
        print("-" * 28)
        for row in rows:
            print(f"{row['manager_name']:<10}{row['fill_status']:<10}{row['cnt']:>6}")
        print("-" * 28)
        print(f"{'合计':<20}{total:>6} 条\n")
    else:
        print("fill_statistics 没有需要清零的 overtime/missing 记录。")

    if args.archive_visits:
        print(f"将归档并移出起算日前 visit_records：{old_visit_count} 条。")
    elif old_visit_count:
        print(
            f"提示：起算日前仍有 visit_records {old_visit_count} 条；"
            "如统计表为空，系统可能从这些预约记录反推历史漏填。"
        )
        print("如需真正从起算日重新算，请加 --archive-visits。")

    if not total and not (args.archive_visits and old_visit_count):
        print("没有需要执行的变更。")
        conn.close()
        return

    if not args.apply:
        print("以上为预览。确认无误后加 --apply 执行。")
        conn.close()
        return

    dest = backup_db()
    print(f"已备份数据库到：{dest}")

    now_text = datetime.now().isoformat(timespec="seconds")
    cursor = conn.execute(
        """UPDATE fill_statistics
           SET fill_status = 'on_time', updated_at = ?
           WHERE date < ? AND fill_status IN ('overtime', 'missing')""",
        (now_text, cutoff),
    )
    print(f"已更新 {cursor.rowcount} 条 fill_statistics 记录为 on_time。")

    archived = 0
    deleted = 0
    if args.archive_visits and old_visit_count:
        safe_cutoff = cutoff.replace("-", "")
        archive_table = f"visit_records_before_{safe_cutoff}_reset"
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {archive_table} AS SELECT * FROM visit_records WHERE 0"
        )
        archive_cursor = conn.execute(
            f"INSERT OR IGNORE INTO {archive_table} SELECT * FROM visit_records WHERE appointment_date < ?",
            (cutoff,),
        )
        archived = archive_cursor.rowcount
        delete_cursor = conn.execute(
            "DELETE FROM visit_records WHERE appointment_date < ?",
            (cutoff,),
        )
        deleted = delete_cursor.rowcount
        print(f"已归档 {archived} 条 visit_records 到 {archive_table}，并从实时表移出 {deleted} 条。")

    conn.commit()

    remain = conn.execute(
        "SELECT COUNT(*) FROM fill_statistics WHERE date < ? AND fill_status IN ('overtime','missing')",
        (cutoff,),
    ).fetchone()[0]
    old_visits_remain = conn.execute(
        "SELECT COUNT(*) FROM visit_records WHERE appointment_date < ?",
        (cutoff,),
    ).fetchone()[0]
    print(f"校验：起算日前剩余 overtime/missing 记录 {remain} 条（应为 0）。")
    if args.archive_visits:
        print(f"校验：起算日前剩余 visit_records {old_visits_remain} 条（应为 0）。")
    conn.close()


if __name__ == "__main__":
    main()
