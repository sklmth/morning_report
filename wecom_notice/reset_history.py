"""历史填报记录清零 —— 一次性运维脚本。

把起算日之前的 overtime / missing 记录标记为 on_time，使其不再计入
「本月记录」和下午茶基金金额。fill_statistics 是这两项的唯一数据来源。

用法（先看效果，再执行）：
    python -m wecom_notice.reset_history --before 2026-08-04
    python -m wecom_notice.reset_history --before 2026-08-04 --apply

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

    total = sum(row["cnt"] for row in rows)
    print(f"数据库：{DB_PATH}")
    print(f"起算日：{cutoff}（此日期之前的记录将标记为 on_time）\n")

    if not total:
        print("没有需要清零的记录。")
        conn.close()
        return

    print(f"{'客户经理':<10}{'状态':<10}{'条数':>6}")
    print("-" * 28)
    for row in rows:
        print(f"{row['manager_name']:<10}{row['fill_status']:<10}{row['cnt']:>6}")
    print("-" * 28)
    print(f"{'合计':<20}{total:>6} 条\n")

    if not args.apply:
        print("以上为预览。确认无误后加 --apply 执行。")
        conn.close()
        return

    dest = backup_db()
    print(f"已备份数据库到：{dest}")

    cursor = conn.execute(
        """UPDATE fill_statistics
           SET fill_status = 'on_time', updated_at = ?
           WHERE date < ? AND fill_status IN ('overtime', 'missing')""",
        (datetime.now().isoformat(timespec="seconds"), cutoff),
    )
    conn.commit()
    print(f"已更新 {cursor.rowcount} 条记录为 on_time。")

    remain = conn.execute(
        "SELECT COUNT(*) FROM fill_statistics WHERE date < ? AND fill_status IN ('overtime','missing')",
        (cutoff,),
    ).fetchone()[0]
    print(f"校验：起算日前剩余 overtime/missing 记录 {remain} 条（应为 0）。")
    conn.close()


if __name__ == "__main__":
    main()
