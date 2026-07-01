"""
完成进度预测模块
基于当前月累数据和日期进度，预测月末完成情况
"""

import calendar
from datetime import date, datetime
from typing import Optional
import sqlite3

from analytics.db import get_connection, query_json
from analytics.config import DUANZHOU_DISTRICT_ALIASES, RISK_THRESHOLDS, NAMES

_NAMES_PLACEHOLDERS = ",".join(f"'{n}'" for n in NAMES)
_NAMES_FILTER = f"name IN ({_NAMES_PLACEHOLDERS})"


def _get_month_days(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _time_progress(data_date_str: str) -> float:
    """计算当前时间进度（已过天数/月总天数）"""
    try:
        d = datetime.strptime(data_date_str, "%Y-%m-%d").date()
        total = _get_month_days(d.year, d.month)
        return round(d.day / total, 4)
    except Exception:
        return 0.0


def _remaining_days(data_date_str: str) -> int:
    """当前日期到月末还剩多少天"""
    try:
        d = datetime.strptime(data_date_str, "%Y-%m-%d").date()
        total = _get_month_days(d.year, d.month)
        return total - d.day
    except Exception:
        return 0


def get_progress_forecast(month: str, conn: Optional[sqlite3.Connection] = None) -> dict:
    """
    完成进度预测：
    - 当前完成值
    - 时间进度
    - 预测月末完成（线性外推）
    - 到达月末需日均完成量
    - 各人员进度
    """
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        # 获取最新数据日期
        row = conn.execute(
            "SELECT MAX(data_date) as d FROM data_snapshots WHERE month=?", (month,)
        ).fetchone()
        latest_date = row["d"] if row and row["d"] else None

        if not latest_date:
            return {"month": month, "has_data": False}

        time_prog = _time_progress(latest_date)
        remaining = _remaining_days(latest_date)
        month_parts = month.split("-")
        year, mo = int(month_parts[0]), int(month_parts[1])
        total_days = _get_month_days(year, mo)

        # 端州区县积分完成情况
        duanzhou_filter = "(" + " OR ".join(f"district='{d}'" for d in DUANZHOU_DISTRICT_ALIASES) + ")"
        dz_pts = query_json(conn, f"""
            SELECT net_pts, inc_pts, base_pts, twin_pts
            FROM district_monthly_metrics
            WHERE month=? AND {duanzhou_filter}
            ORDER BY data_date DESC
            LIMIT 1
        """, (month,))

        # 人员月累完成情况（仅14人，使用政企认领口径高套 col7+col8）
        person_data = query_json(conn, f"""
            SELECT pm.name,
                MAX(pm.new_gaotao_zq + pm.stock_gaotao_zq) as total_gaotao,
                MAX(pm.inc_pts_total) as inc_pts,
                MAX(pm.new_pts_total) as new_pts,
                se.predicted_incentive
            FROM person_monthly_metrics pm
            LEFT JOIN (
                SELECT name, MAX(predicted_incentive) as predicted_incentive
                FROM staff_efficiency WHERE month=? AND {_NAMES_FILTER}
                GROUP BY name
            ) se ON pm.name = se.name
            WHERE pm.month=? AND pm.{_NAMES_FILTER}
            GROUP BY pm.name
            ORDER BY inc_pts DESC
        """, (month, month))

        # 人员高套档位情况（最新）
        tier_data = query_json(conn, f"""
            SELECT name,
                SUM(tier_129_pts) as tier_129,
                SUM(tier_169_pts) as tier_169,
                SUM(tier_199_pts) as tier_199
            FROM staff_incentive_tier
            WHERE month=? AND {_NAMES_FILTER}
            GROUP BY name
        """, (month,))
        tier_map = {t['name']: t for t in tier_data}

        # 积分预测
        forecast_pts = {}
        if dz_pts and time_prog > 0:
            current_net = dz_pts[0].get('net_pts') or 0
            projected = round(current_net / time_prog, 2)
            daily_avg = round(current_net / (total_days - remaining), 2) if (total_days - remaining) > 0 else 0
            forecast_pts = {
                "current": round(current_net, 2),
                "time_progress": round(time_prog * 100, 1),
                "projected_month_end": projected,
                "daily_avg_actual": daily_avg,
                "remaining_days": remaining,
            }

        # 逐人进度
        person_progress = []
        for p in person_data:
            gaotao_val = p.get('total_gaotao') or 0
            pts_val = p.get('inc_pts') or 0
            projected_gaotao = round(gaotao_val / time_prog, 1) if time_prog > 0 else 0
            projected_pts = round(pts_val / time_prog, 1) if time_prog > 0 else 0
            tier = tier_map.get(p['name'], {})

            # 进度状态
            pts_vs_time = (pts_val / projected_pts - 1) if projected_pts else 0
            if pts_vs_time >= -RISK_THRESHOLDS['progress_gap']:
                status = "green"
            elif pts_vs_time >= -2 * RISK_THRESHOLDS['progress_gap']:
                status = "yellow"
            else:
                status = "red"

            person_progress.append({
                "name": p['name'],
                "total_gaotao": gaotao_val,
                "inc_pts": round(pts_val, 2),
                "projected_gaotao_month": projected_gaotao,
                "projected_pts_month": projected_pts,
                "predicted_incentive": round(p.get('predicted_incentive') or 0, 0),
                "tier_129": tier.get('tier_129') or 0,
                "tier_169": tier.get('tier_169') or 0,
                "tier_199": tier.get('tier_199') or 0,
                "status": status,
                "progress_vs_time": round(pts_vs_time * 100, 1),
            })

        return {
            "month": month,
            "has_data": True,
            "latest_date": latest_date,
            "time_progress": round(time_prog * 100, 1),
            "remaining_days": remaining,
            "total_days": total_days,
            "pts_forecast": forecast_pts,
            "person_progress": person_progress,
        }
    finally:
        if close:
            conn.close()
