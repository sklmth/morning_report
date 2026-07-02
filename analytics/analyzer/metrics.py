"""
分析指标计算模块
从analytics.db中读取原始数据，计算各类经营分析指标
"""

from typing import Optional
import sqlite3
from analytics.db import get_connection, get_latest_snapshot_date, get_latest_snapshot_id, query_json
from analytics.config import DUANZHOU_DISTRICT_ALIASES, BRANCH_NAMES, RISK_THRESHOLDS, NAMES

# SQL 片段：仅分析14个政企客户经理
_NAMES_PLACEHOLDERS = ",".join(f"'{n}'" for n in NAMES)
_NAMES_FILTER = f"name IN ({_NAMES_PLACEHOLDERS})"


# ─── 积分结构分析 ──────────────────────────────────────────────────────────────

def get_score_structure(month: str, conn: Optional[sqlite3.Connection] = None) -> dict:
    """
    返回端州分公司积分结构分析：
    - 各积分分项构成（基本面/双线/其他）
    - 健康度指标（拆机占比/到期占比/降值占比）
    - 与全市对比
    """
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        wanmei_snapshot_id = get_latest_snapshot_id(conn, month, "wanmei")
        if not wanmei_snapshot_id:
            return {"month": month, "duanzhou": {}, "all_districts": [], "health": {}, "warnings": []}

        # 端州积分结构
        duanzhou_filter = "(" + " OR ".join(f"district='{d}'" for d in DUANZHOU_DISTRICT_ALIASES) + ")"
        dz_rows = query_json(conn, f"""
            SELECT
                net_pts, base_pts, base_mobile, base_bb, base_phone, base_itv, base_smart,
                base_expire, base_decline, base_churn, twin_pts, twin_inet, twin_net,
                twin_decline, twin_churn, other_pts, inc_pts,
                COUNT(*) as snapshot_count
            FROM district_monthly_metrics
            WHERE snapshot_id=? AND {duanzhou_filter}
        """, (wanmei_snapshot_id,))

        dz = dz_rows[0] if dz_rows else {}

        # 全市各县分积分
        all_districts = query_json(conn, """
            SELECT district, net_pts, inc_pts, base_pts, twin_pts, other_pts,
                base_churn, base_decline, base_expire
            FROM district_monthly_metrics
            WHERE snapshot_id=?
            GROUP BY district
            ORDER BY net_pts DESC
        """, (wanmei_snapshot_id,))

        # 健康度计算
        inc = dz.get('inc_pts') or 1  # 避免除零
        churn_ratio = abs(dz.get('base_churn', 0) or 0) / max(inc, 1)
        decline_ratio = abs(dz.get('base_decline', 0) or 0) / max(inc, 1)
        expire_ratio = abs(dz.get('base_expire', 0) or 0) / max(inc, 1)

        warnings = []
        if churn_ratio > RISK_THRESHOLDS['churn_ratio']:
            warnings.append({"type": "拆机过高", "value": round(churn_ratio * 100, 1), "threshold": RISK_THRESHOLDS['churn_ratio'] * 100})
        if decline_ratio > RISK_THRESHOLDS['decline_ratio']:
            warnings.append({"type": "降值过高", "value": round(decline_ratio * 100, 1), "threshold": RISK_THRESHOLDS['decline_ratio'] * 100})
        if expire_ratio > RISK_THRESHOLDS['expire_ratio']:
            warnings.append({"type": "到期积分占比过高", "value": round(expire_ratio * 100, 1), "threshold": RISK_THRESHOLDS['expire_ratio'] * 100})

        return {
            "month": month,
            "duanzhou": {
                "net_pts": round(dz.get('net_pts') or 0, 2),
                "inc_pts": round(dz.get('inc_pts') or 0, 2),
                "base_pts": round(dz.get('base_pts') or 0, 2),
                "base_mobile": round(dz.get('base_mobile') or 0, 2),
                "base_bb": round(dz.get('base_bb') or 0, 2),
                "base_phone": round(dz.get('base_phone') or 0, 2),
                "base_itv": round(dz.get('base_itv') or 0, 2),
                "base_smart": round(dz.get('base_smart') or 0, 2),
                "base_expire": round(dz.get('base_expire') or 0, 2),
                "base_decline": round(dz.get('base_decline') or 0, 2),
                "base_churn": round(dz.get('base_churn') or 0, 2),
                "twin_pts": round(dz.get('twin_pts') or 0, 2),
                "twin_inet": round(dz.get('twin_inet') or 0, 2),
                "twin_net": round(dz.get('twin_net') or 0, 2),
                "other_pts": round(dz.get('other_pts') or 0, 2),
            },
            "all_districts": all_districts,
            "health": {
                "churn_ratio": round(churn_ratio * 100, 1),
                "decline_ratio": round(decline_ratio * 100, 1),
                "expire_ratio": round(expire_ratio * 100, 1),
            },
            "warnings": warnings,
        }
    finally:
        if close:
            conn.close()


# ─── 人员效能分析 ──────────────────────────────────────────────────────────────

def get_person_efficiency(month: str, conn: Optional[sqlite3.Connection] = None) -> dict:
    """
    返回人员效能分析数据：
    - 揽装积分 vs 高套 散点图数据
    - 人员激励排名
    - 高套档位分布
    - CP对完成率排名
    """
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        wanmei_snapshot_id = get_latest_snapshot_id(conn, month, "wanmei")
        yingfu_snapshot_id = get_latest_snapshot_id(conn, month, "yingfu")

        # 营服人员效能（最新快照，仅14人）
        staff = query_json(conn, f"""
            SELECT name, center, role,
                predicted_incentive, total_gaotao, new_gaotao, stock_gaotao,
                device_pts, incentive_pts, fttr, mobile
            FROM staff_efficiency
            WHERE snapshot_id=? AND {_NAMES_FILTER}
            ORDER BY predicted_incentive DESC
        """, (yingfu_snapshot_id,)) if yingfu_snapshot_id else []

        # 高套档位分布（仅14人）
        tiers = query_json(conn, f"""
            SELECT name, center,
                tier_129_pts as tier_129,
                tier_169_pts as tier_169,
                tier_199_pts as tier_199,
                dev_incentive
            FROM staff_incentive_tier
            WHERE snapshot_id=? AND {_NAMES_FILTER}
            ORDER BY dev_incentive DESC
        """, (yingfu_snapshot_id,)) if yingfu_snapshot_id else []

        # CP对效能（最新快照）
        cp_pairs = query_json(conn, """
            SELECT center, cp_group, sales_name, install_name,
                cp_target, cp_pts_total, cp_gap,
                sales_pts_actual, sales_target,
                CASE WHEN cp_target > 0
                     THEN ROUND(cp_pts_total * 100.0 / cp_target, 1)
                     ELSE 0 END as completion_rate
            FROM cp_pair_metrics
            WHERE snapshot_id=?
            ORDER BY completion_rate DESC
        """, (yingfu_snapshot_id,)) if yingfu_snapshot_id else []

        # 完美一单人员数据（仅14人，使用政企认领口径高套 col7+col8）
        wanmei_staff = query_json(conn, f"""
            SELECT name,
                new_gaotao_zq as new_gaotao,
                stock_gaotao_zq as stock_gaotao,
                inc_pts_total, inc_pts_base, inc_pts_twin, new_pts_total, gateway_count
            FROM person_monthly_metrics
            WHERE snapshot_id=? AND {_NAMES_FILTER}
            ORDER BY inc_pts_total DESC
        """, (wanmei_snapshot_id,)) if wanmei_snapshot_id else []

        return {
            "month": month,
            "staff_efficiency": staff,
            "incentive_tiers": tiers,
            "cp_pairs": cp_pairs,
            "wanmei_staff": wanmei_staff,
        }
    finally:
        if close:
            conn.close()


# ─── 存量风险预警 ──────────────────────────────────────────────────────────────

def get_risk_alerts(month: str, conn: Optional[sqlite3.Connection] = None) -> dict:
    """
    存量风险预警：
    - 按人员统计存量流失情况
    - 按业务类型分析风险点
    - 综合风险评分
    """
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        wanmei_snapshot_id = get_latest_snapshot_id(conn, month, "wanmei")
        if not wanmei_snapshot_id:
            return {"month": month, "duanzhou_risk": {}, "historical_trend": [], "person_stock": [], "alerts": []}

        # 端州区县层级风险
        duanzhou_filter = "(" + " OR ".join(f"district='{d}'" for d in DUANZHOU_DISTRICT_ALIASES) + ")"
        dz_risk = query_json(conn, f"""
            SELECT month, data_date,
                net_pts, inc_pts, base_pts, twin_pts,
                base_expire, base_decline, base_churn,
                twin_decline, twin_churn, other_pts,
                CASE WHEN inc_pts != 0
                     THEN ROUND(ABS(base_churn) * 100.0 / ABS(inc_pts), 1)
                     ELSE 0 END as churn_ratio,
                CASE WHEN inc_pts != 0
                     THEN ROUND(ABS(base_decline) * 100.0 / ABS(inc_pts), 1)
                     ELSE 0 END as decline_ratio
            FROM district_monthly_metrics
            WHERE snapshot_id=? AND {duanzhou_filter}
            ORDER BY data_date DESC
            LIMIT 1
        """, (wanmei_snapshot_id,))

        # 按月份趋势（历史对比）
        historical = query_json(conn, f"""
            SELECT dm.month,
                dm.net_pts, dm.base_churn, dm.base_decline, dm.base_expire, dm.inc_pts
            FROM district_monthly_metrics dm
            JOIN (
                SELECT month, MAX(id) as snapshot_id
                FROM data_snapshots
                WHERE source_type='wanmei'
                GROUP BY month
            ) latest ON latest.snapshot_id = dm.snapshot_id
            WHERE {duanzhou_filter}
            GROUP BY dm.month
            ORDER BY dm.month DESC
            LIMIT 6
        """)

        # 人员层级存量积分（仅14人）
        person_stock = query_json(conn, f"""
            SELECT name, month,
                stock_pts_total as stock_pts,
                new_gaotao, stock_gaotao, inc_pts_total as inc_pts
            FROM person_monthly_metrics
            WHERE snapshot_id=? AND {_NAMES_FILTER}
            ORDER BY stock_pts ASC
        """, (wanmei_snapshot_id,))

        # 生成预警列表
        alerts = []
        if dz_risk:
            r = dz_risk[0]
            if r.get('churn_ratio', 0) > RISK_THRESHOLDS['churn_ratio'] * 100:
                alerts.append({
                    "level": "red", "type": "基本面拆机占比过高",
                    "value": f"{r['churn_ratio']}%",
                    "desc": f"拆机积分占增量积分比例为{r['churn_ratio']}%，超过预警线{RISK_THRESHOLDS['churn_ratio']*100:.0f}%"
                })
            if r.get('decline_ratio', 0) > RISK_THRESHOLDS['decline_ratio'] * 100:
                alerts.append({
                    "level": "orange", "type": "降值积分占比过高",
                    "value": f"{r['decline_ratio']}%",
                    "desc": f"降值积分占增量积分比例为{r['decline_ratio']}%，存量价值流失明显"
                })
            if (r.get('net_pts', 0) or 0) < 0:
                alerts.append({
                    "level": "red", "type": "净增积分为负",
                    "value": f"{round(r.get('net_pts', 0), 0)}分",
                    "desc": "净增积分为负，说明存量流失大于新增，需要重点关注"
                })

        return {
            "month": month,
            "duanzhou_risk": dz_risk[0] if dz_risk else {},
            "historical_trend": historical,
            "person_stock": person_stock,
            "alerts": alerts,
        }
    finally:
        if close:
            conn.close()


# ─── 横向对比 ──────────────────────────────────────────────────────────────────

def get_branch_compare(month: str, conn: Optional[sqlite3.Connection] = None) -> dict:
    """
    全市各县分横向对比：
    - 净增积分排名
    - 各业务维度对比
    - 端州在全市的位置
    """
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        wanmei_snapshot_id = get_latest_snapshot_id(conn, month, "wanmei")
        if not wanmei_snapshot_id:
            return {"month": month, "branches": [], "total_branches": 0, "duanzhou_rank": None}

        branches = query_json(conn, """
            SELECT district,
                net_pts, inc_pts, base_pts, twin_pts, other_pts, base_churn, base_expire
            FROM district_monthly_metrics
            WHERE snapshot_id=?
            GROUP BY district
            ORDER BY net_pts DESC
        """, (wanmei_snapshot_id,))

        # 找端州排名
        duanzhou_rank = None
        for i, b in enumerate(branches):
            if b['district'] in DUANZHOU_DISTRICT_ALIASES:
                duanzhou_rank = i + 1
                break

        return {
            "month": month,
            "branches": branches,
            "total_branches": len(branches),
            "duanzhou_rank": duanzhou_rank,
        }
    finally:
        if close:
            conn.close()


# ─── 总览 ──────────────────────────────────────────────────────────────────────

def get_overview(month: Optional[str] = None, conn: Optional[sqlite3.Connection] = None) -> dict:
    """
    总览：最新一期核心KPI
    """
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        # 最新月份
        if not month:
            row = conn.execute(
                "SELECT MAX(month) as m FROM data_snapshots"
            ).fetchone()
            month = row["m"] if row and row["m"] else None

        if not month:
            return {"month": None, "has_data": False}

        wanmei_snapshot_id = get_latest_snapshot_id(conn, month, "wanmei")
        yingfu_snapshot_id = get_latest_snapshot_id(conn, month, "yingfu")
        latest_date = get_latest_snapshot_date(conn, month)

        # 端州积分 + 落格率
        duanzhou_filter = "(" + " OR ".join(f"district='{d}'" for d in DUANZHOU_DISTRICT_ALIASES) + ")"
        dz_pts = query_json(conn, f"""
            SELECT AVG(net_pts) as net_pts,
                   AVG(base_pts) as base_pts,
                   AVG(twin_pts) as twin_pts,
                   AVG(other_pts) as other_pts,
                   AVG(pts_completion_rate) as completion_rate
            FROM district_monthly_metrics
            WHERE snapshot_id=? AND {duanzhou_filter}
        """, (wanmei_snapshot_id,)) if wanmei_snapshot_id else []

        # 总高套（政企认领口径 col7+col8，仅14人）
        gaotao = query_json(conn, f"""
            SELECT SUM(new_gaotao_zq + stock_gaotao_zq) as total_gaotao,
                   SUM(inc_pts_total) as team_pts_done,
                   COUNT(DISTINCT name) as person_count
            FROM person_monthly_metrics
            WHERE snapshot_id=? AND {_NAMES_FILTER}
        """, (wanmei_snapshot_id,)) if wanmei_snapshot_id else []

        # 人均激励（仅14人）
        incentive = query_json(conn, f"""
            SELECT AVG(predicted_incentive) as avg_incentive,
                   SUM(predicted_incentive) as total_incentive,
                   COUNT(*) as person_count
            FROM staff_efficiency
            WHERE snapshot_id=? AND {_NAMES_FILTER}
        """, (yingfu_snapshot_id,)) if yingfu_snapshot_id else []

        # 快照数量
        snap_count = conn.execute(
            "SELECT COUNT(*) as c FROM data_snapshots WHERE month=?", (month,)
        ).fetchone()

        dz = dz_pts[0] if dz_pts else {}
        gt = gaotao[0] if gaotao else {}
        inc = incentive[0] if incentive else {}
        return {
            "month": month,
            "latest_date": latest_date,
            "has_data": True,
            "net_pts": round(dz.get('net_pts') or 0, 2),
            "base_pts": round(dz.get('base_pts') or 0, 2),
            "twin_pts": round(dz.get('twin_pts') or 0, 2),
            "other_pts": round(dz.get('other_pts') or 0, 2),
            "completion_rate": round((dz.get('completion_rate') or 0) * 100, 1),  # 转为百分比
            "team_pts_done": round(gt.get('team_pts_done') or 0, 2),   # 积分完成（14人col13合计）
            "total_gaotao": round(gt.get('total_gaotao') or 0, 1),     # 政企认领口径
            "avg_incentive": round(inc.get('avg_incentive') or 0, 0),
            "total_incentive": round(inc.get('total_incentive') or 0, 0),
            "snapshot_count": snap_count["c"] if snap_count else 0,
        }
    finally:
        if close:
            conn.close()


# ─── 历史趋势 ──────────────────────────────────────────────────────────────────

def get_trend(months: int = 6, conn: Optional[sqlite3.Connection] = None) -> dict:
    """
    多月度历史趋势数据（用于折线图）
    """
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        duanzhou_filter = "(" + " OR ".join(f"district='{d}'" for d in DUANZHOU_DISTRICT_ALIASES) + ")"

        # 端州积分月度趋势
        pts_trend = query_json(conn, f"""
            SELECT dm.month,
                dm.net_pts, dm.inc_pts, dm.base_pts, dm.twin_pts, dm.other_pts
            FROM district_monthly_metrics dm
            JOIN (
                SELECT month, MAX(id) as snapshot_id
                FROM data_snapshots
                WHERE source_type='wanmei'
                GROUP BY month
            ) latest ON latest.snapshot_id = dm.snapshot_id
            WHERE {duanzhou_filter}
            GROUP BY dm.month
            ORDER BY dm.month ASC
            LIMIT ?
        """, (months,))

        # 端州政企高套月度趋势（政企责任田认领口径 new_gaotao_zq+stock_gaotao_zq，仅14人）
        gaotao_trend = query_json(conn, f"""
            SELECT pm.month,
                SUM(pm.new_gaotao_zq) as new_gaotao,
                SUM(pm.stock_gaotao_zq) as stock_gaotao
            FROM person_monthly_metrics pm
            JOIN (
                SELECT month, MAX(id) as snapshot_id
                FROM data_snapshots
                WHERE source_type='wanmei'
                GROUP BY month
            ) latest ON latest.snapshot_id = pm.snapshot_id
            WHERE pm.{_NAMES_FILTER}
            GROUP BY pm.month
            ORDER BY pm.month ASC
            LIMIT ?
        """, (months,))

        # 激励月度趋势
        incentive_trend = query_json(conn, """
            SELECT se.month,
                AVG(se.predicted_incentive) as avg_incentive,
                SUM(se.predicted_incentive) as total_incentive
            FROM staff_efficiency se
            JOIN (
                SELECT month, MAX(id) as snapshot_id
                FROM data_snapshots
                WHERE source_type='yingfu'
                GROUP BY month
            ) latest ON latest.snapshot_id = se.snapshot_id
            GROUP BY se.month
            ORDER BY se.month ASC
            LIMIT ?
        """, (months,))

        return {
            "pts_trend": pts_trend,
            "gaotao_trend": gaotao_trend,
            "incentive_trend": incentive_trend,
        }
    finally:
        if close:
            conn.close()
