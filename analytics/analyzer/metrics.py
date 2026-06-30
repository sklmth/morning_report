"""
分析指标计算模块
从analytics.db中读取原始数据，计算各类经营分析指标
"""

from typing import Optional
import sqlite3
from analytics.db import get_connection, query_json
from analytics.config import DUANZHOU_DISTRICT_ALIASES, BRANCH_NAMES, RISK_THRESHOLDS


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
        # 端州积分结构
        duanzhou_filter = "(" + " OR ".join(f"district='{d}'" for d in DUANZHOU_DISTRICT_ALIASES) + ")"
        dz_rows = query_json(conn, f"""
            SELECT
                AVG(net_pts) as net_pts,
                AVG(base_pts) as base_pts,
                AVG(base_mobile) as base_mobile,
                AVG(base_bb) as base_bb,
                AVG(base_phone) as base_phone,
                AVG(base_itv) as base_itv,
                AVG(base_smart) as base_smart,
                AVG(base_expire) as base_expire,
                AVG(base_decline) as base_decline,
                AVG(base_churn) as base_churn,
                AVG(twin_pts) as twin_pts,
                AVG(twin_inet) as twin_inet,
                AVG(twin_net) as twin_net,
                AVG(twin_decline) as twin_decline,
                AVG(twin_churn) as twin_churn,
                AVG(other_pts) as other_pts,
                AVG(inc_pts) as inc_pts,
                COUNT(*) as snapshot_count
            FROM district_monthly_metrics
            WHERE month=? AND {duanzhou_filter}
        """, (month,))

        dz = dz_rows[0] if dz_rows else {}

        # 全市各县分积分
        all_districts = query_json(conn, """
            SELECT district,
                AVG(net_pts) as net_pts,
                AVG(inc_pts) as inc_pts,
                AVG(base_pts) as base_pts,
                AVG(twin_pts) as twin_pts,
                AVG(other_pts) as other_pts,
                AVG(base_churn) as base_churn,
                AVG(base_decline) as base_decline,
                AVG(base_expire) as base_expire
            FROM district_monthly_metrics
            WHERE month=?
            GROUP BY district
            ORDER BY net_pts DESC
        """, (month,))

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
        # 营服人员效能（最新快照）
        staff = query_json(conn, """
            SELECT name, center, role,
                MAX(predicted_incentive) as predicted_incentive,
                MAX(total_gaotao) as total_gaotao,
                MAX(new_gaotao) as new_gaotao,
                MAX(stock_gaotao) as stock_gaotao,
                MAX(device_pts) as device_pts,
                MAX(incentive_pts) as incentive_pts,
                MAX(fttr) as fttr,
                MAX(mobile) as mobile
            FROM staff_efficiency
            WHERE month=?
            GROUP BY name
            ORDER BY predicted_incentive DESC
        """, (month,))

        # 高套档位分布
        tiers = query_json(conn, """
            SELECT name, center,
                SUM(tier_129_pts) as tier_129,
                SUM(tier_169_pts) as tier_169,
                SUM(tier_199_pts) as tier_199,
                SUM(dev_incentive) as dev_incentive
            FROM staff_incentive_tier
            WHERE month=?
            GROUP BY name
            ORDER BY dev_incentive DESC
        """, (month,))

        # CP对效能（最新快照）
        cp_pairs = query_json(conn, """
            SELECT center, cp_group, sales_name, install_name,
                cp_target, cp_pts_total, cp_gap,
                sales_pts_actual, sales_target,
                CASE WHEN cp_target > 0
                     THEN ROUND(cp_pts_total * 100.0 / cp_target, 1)
                     ELSE 0 END as completion_rate
            FROM cp_pair_metrics
            WHERE month=?
            ORDER BY completion_rate DESC
        """, (month,))

        # 完美一单人员数据（包含更多字段）
        wanmei_staff = query_json(conn, """
            SELECT name,
                MAX(new_gaotao) as new_gaotao,
                MAX(stock_gaotao) as stock_gaotao,
                MAX(inc_pts_total) as inc_pts_total,
                MAX(inc_pts_base) as inc_pts_base,
                MAX(inc_pts_twin) as inc_pts_twin,
                MAX(new_pts_total) as new_pts_total,
                MAX(gateway_count) as gateway_count
            FROM person_monthly_metrics
            WHERE month=?
            GROUP BY name
            ORDER BY inc_pts_total DESC
        """, (month,))

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
            WHERE month=? AND {duanzhou_filter}
            ORDER BY data_date DESC
            LIMIT 1
        """, (month,))

        # 按月份趋势（历史对比）
        historical = query_json(conn, f"""
            SELECT month,
                AVG(net_pts) as net_pts,
                AVG(base_churn) as base_churn,
                AVG(base_decline) as base_decline,
                AVG(base_expire) as base_expire,
                AVG(inc_pts) as inc_pts
            FROM district_monthly_metrics
            WHERE {duanzhou_filter}
            GROUP BY month
            ORDER BY month DESC
            LIMIT 6
        """)

        # 人员层级存量积分（从完美一单）
        person_stock = query_json(conn, """
            SELECT name, month,
                MAX(stock_pts_total) as stock_pts,
                MAX(new_gaotao) as new_gaotao,
                MAX(stock_gaotao) as stock_gaotao,
                MAX(inc_pts_total) as inc_pts
            FROM person_monthly_metrics
            WHERE month=?
            GROUP BY name
            ORDER BY stock_pts ASC
        """, (month,))

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
        branches = query_json(conn, """
            SELECT district,
                AVG(net_pts) as net_pts,
                AVG(inc_pts) as inc_pts,
                AVG(base_pts) as base_pts,
                AVG(twin_pts) as twin_pts,
                AVG(other_pts) as other_pts,
                AVG(base_churn) as base_churn,
                AVG(base_expire) as base_expire
            FROM district_monthly_metrics
            WHERE month=?
            GROUP BY district
            ORDER BY net_pts DESC
        """, (month,))

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

        # 最新数据日期
        row = conn.execute(
            "SELECT MAX(data_date) as d FROM data_snapshots WHERE month=?", (month,)
        ).fetchone()
        latest_date = row["d"] if row else None

        # 端州积分
        duanzhou_filter = "(" + " OR ".join(f"district='{d}'" for d in DUANZHOU_DISTRICT_ALIASES) + ")"
        dz_pts = query_json(conn, f"""
            SELECT AVG(net_pts) as net_pts, AVG(inc_pts) as inc_pts
            FROM district_monthly_metrics
            WHERE month=? AND {duanzhou_filter}
        """, (month,))

        # 总高套
        gaotao = query_json(conn, """
            SELECT SUM(new_gaotao + stock_gaotao) as total_gaotao,
                   COUNT(DISTINCT name) as person_count
            FROM person_monthly_metrics
            WHERE month=?
        """, (month,))

        # 人均激励
        incentive = query_json(conn, """
            SELECT AVG(predicted_incentive) as avg_incentive,
                   SUM(predicted_incentive) as total_incentive,
                   COUNT(*) as person_count
            FROM staff_efficiency
            WHERE month=?
        """, (month,))

        # 快照数量
        snap_count = conn.execute(
            "SELECT COUNT(*) as c FROM data_snapshots WHERE month=?", (month,)
        ).fetchone()

        return {
            "month": month,
            "latest_date": latest_date,
            "has_data": True,
            "net_pts": round((dz_pts[0].get('net_pts') or 0) if dz_pts else 0, 2),
            "inc_pts": round((dz_pts[0].get('inc_pts') or 0) if dz_pts else 0, 2),
            "total_gaotao": round((gaotao[0].get('total_gaotao') or 0) if gaotao else 0, 0),
            "avg_incentive": round((incentive[0].get('avg_incentive') or 0) if incentive else 0, 0),
            "total_incentive": round((incentive[0].get('total_incentive') or 0) if incentive else 0, 0),
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
            SELECT month,
                AVG(net_pts) as net_pts,
                AVG(inc_pts) as inc_pts,
                AVG(base_pts) as base_pts,
                AVG(twin_pts) as twin_pts,
                AVG(other_pts) as other_pts
            FROM district_monthly_metrics
            WHERE {duanzhou_filter}
            GROUP BY month
            ORDER BY month ASC
            LIMIT ?
        """, (months,))

        # 人员高套月度趋势
        gaotao_trend = query_json(conn, """
            SELECT month,
                SUM(new_gaotao) as new_gaotao,
                SUM(stock_gaotao) as stock_gaotao,
                COUNT(DISTINCT name) as person_count
            FROM person_monthly_metrics
            GROUP BY month
            ORDER BY month ASC
            LIMIT ?
        """, (months,))

        # 激励月度趋势
        incentive_trend = query_json(conn, """
            SELECT month,
                AVG(predicted_incentive) as avg_incentive,
                SUM(predicted_incentive) as total_incentive
            FROM staff_efficiency
            GROUP BY month
            ORDER BY month ASC
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
