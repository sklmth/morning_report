"""
政企营服标准化运营日通报（文字版）动态生成。

固定话术（策略、协同、闭环等段落）保持原样；其中的数值严格按「模板1」大表
（A1:R21「完美一单积分完成通报」区域）的公式口径，从结果 Excel 各数据 sheet
动态重算后填入。日期取「截至昨天」。

模板1 公式口径（已逐一核对）：
  C 高套目标：个人 10；党政军合计 70；大企业合计 70；全合计 132（手填）
  D 高套发展 = XLOOKUP(姓名, 高套!A:B)
  E 高套完成率 = D / C
  F 高套时间进度完成率 = D / (C/X5*U5) = E / factor，factor = U5/X5
  J 积分目标：个人 2500
  K 积分完成 = VLOOKUP(姓名, 完美一单!A:C, 3)；邱海燕额外 +2500（K7 特批）
  L 积分完成率 = K / J
  M 积分时间进度完成率 = K / (J/X5*U5) = L / factor
  P 全光目标：个人 21；端州 310
  Q 全光主从网关数 = XLOOKUP(姓名, 全光组网!A:B)
  R 全光完成率 = Q / P
  X5 = 当月总天数；U5 = 昨天（当月已过天数）
"""

import calendar
import glob
import os
from datetime import date, timedelta

import pandas as pd

# ── 模板1 团队分组（row4-10 党政军；row12-18 大企业）──────────────────
TEAM_PARTY = ["钟俊杰", "麦海芬", "黄淡妮", "邱海燕", "李东", "王锦添", "黄观霞"]
TEAM_ENTERPRISE = ["冯艺康", "谢卓和", "伍颖敏", "潘观友", "李玉强", "张小敏", "具进康"]
ALL_PERSONS = TEAM_PARTY + TEAM_ENTERPRISE

# ── 模板1 目标（C/J/P 列）──────────────────────────────────────────────
GAOTAO_TARGET_PER_PERSON = 10        # C 列个人高套目标
GAOTAO_TARGET_PARTY = 70             # C11 党政军合计
GAOTAO_TARGET_ENTERPRISE = 70        # C19 大企业合计
GAOTAO_TARGET_TOTAL = 132            # C20 全合计（手填）
PERFECT_TARGET_PER_PERSON = 2500     # J 列个人积分目标
QUANGUANG_TARGET_PER_PERSON = 21     # P 列个人全光目标
QUANGUANG_DZ_TARGET = 310            # P21 端州目标

# 邱海燕 6 月特批固定加分（模板 K7 = VLOOKUP+2500）
PERFECT_BONUS = {"邱海燕": 2500}


def _factor():
    """时间进度系数 factor = 当月已过天数(U5=昨天) / 当月总天数(X5)。"""
    today = date.today()
    u5 = (today - timedelta(days=1)).day
    x5 = calendar.monthrange(today.year, today.month)[1]
    return u5 / x5


def _report_date_str():
    y = date.today() - timedelta(days=1)
    return f"{y.month}月{y.day}日"


def _pct(x):
    return f"{round(x * 100)}%"


def _fmt_num(v):
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _sheet_map(xlsx, sheet, val_idx=1):
    """读 sheet，返回 {姓名: 值}。val_idx 指定取第几列（默认第2列）。"""
    df = pd.read_excel(xlsx, sheet_name=sheet)
    cols = list(df.columns)
    kcol, vcol = cols[0], cols[val_idx]
    m = {}
    for _, r in df.iterrows():
        k = str(r[kcol]).strip()
        try:
            m[k] = float(r[vcol])
        except (TypeError, ValueError):
            m[k] = 0.0
    return m


def _top(name_val, members, n):
    items = [(k, name_val.get(k, 0.0)) for k in members]
    items.sort(key=lambda x: x[1], reverse=True)
    return [(k, v) for k, v in items if v > 0][:n]


def build_report_text(result_xlsx):
    factor = _factor()
    date_str = _report_date_str()

    # ── 数据源（D/K/Q 列）──
    d_gaotao = _sheet_map(result_xlsx, "高套")              # D 列
    k_perfect = _sheet_map(result_xlsx, "完美一单", val_idx=2)  # K 列（积分完成）
    q_quang = _sheet_map(result_xlsx, "全光组网")           # Q 列
    for nm, bonus in PERFECT_BONUS.items():                  # 邱海燕 +2500
        k_perfect[nm] = k_perfect.get(nm, 0.0) + bonus

    def sum_members(m, members):
        return sum(m.get(n, 0.0) for n in members)

    # ── 一、政企高套（D/E/F）──
    gaotao_total = sum_members(d_gaotao, ALL_PERSONS)
    gaotao_rate = gaotao_total / GAOTAO_TARGET_TOTAL
    gaotao_time = gaotao_rate / factor if factor else 0
    gaotao_top = _top(d_gaotao, ALL_PERSONS, 7)
    gaotao_top_str = "、".join(f"{n}（{_fmt_num(v)}户）" for n, v in gaotao_top)

    # ── 二、完美一单积分（K/L/M）──
    perfect_total = sum_members(k_perfect, ALL_PERSONS)
    perfect_target_total = PERFECT_TARGET_PER_PERSON * len(ALL_PERSONS)
    perfect_rate = perfect_total / perfect_target_total
    perfect_time = perfect_rate / factor if factor else 0
    # 第一梯队：个人 M 列（时间进度完成率）= K / (2500*factor)
    denom = PERFECT_TARGET_PER_PERSON * factor if factor else PERFECT_TARGET_PER_PERSON
    tier = [(n, k_perfect.get(n, 0.0) / denom) for n in ALL_PERSONS]
    tier.sort(key=lambda x: x[1], reverse=True)
    first_tier = tier[:5]
    first_tier_str = "、".join(f"{n}（{_pct(r)}）" for n, r in first_tier)

    # ── 三、全光组网（Q/R）──
    dz_total = q_quang.get("端州", 0.0)
    dz_rate = dz_total / QUANGUANG_DZ_TARGET
    qg_zhengqi = sum_members(q_quang, ALL_PERSONS)
    qg_zhengqi_rate = qg_zhengqi / QUANGUANG_DZ_TARGET
    qg_top = _top(q_quang, ALL_PERSONS, 6)
    qg_top_str = "、".join(f"{n}（{_fmt_num(v)}户）" for n, v in qg_top)

    # ── 五、团队对标（按模板1 合计行口径）──
    def team_stat(members, gaotao_target):
        gt = sum_members(d_gaotao, members)
        gt_rate = gt / gaotao_target
        gt_time = gt_rate / factor if factor else 0
        pf = sum_members(k_perfect, members)
        pf_target = PERFECT_TARGET_PER_PERSON * len(members)
        pf_rate = pf / pf_target
        pf_time = pf_rate / factor if factor else 0
        qg = sum_members(q_quang, members)
        qg_target = QUANGUANG_TARGET_PER_PERSON * len(members)  # P19=SUM(P12:P18)=7*21
        qg_rate = qg / qg_target if qg_target else 0
        return dict(gt_rate=gt_rate, gt_time=gt_time, pf_rate=pf_rate,
                    pf_time=pf_time, qg_rate=qg_rate)

    ent = team_stat(TEAM_ENTERPRISE, GAOTAO_TARGET_ENTERPRISE)
    party = team_stat(TEAM_PARTY, GAOTAO_TARGET_PARTY)

    # ── 组装 ──
    text = f"""【政企营服标准化运营日通报（{date_str}）】

一、 政企高套业务
整体进度： 全员累计发展 {_fmt_num(gaotao_total)} 户，整体完成率为 {_pct(gaotao_rate)}，时间进度完成率 {_pct(gaotao_time)}。整体进度仍有较大提升空间，需紧迫提升攻坚势头，全力冲刺全月目标达成。
攻坚先锋： {gaotao_top_str} 产出位居前列，是当前业务增长的核心引擎。

二、 完美一单积分
整体进度： 累计完成积分 {_fmt_num(perfect_total)} 分，时间进度完成率为 {_pct(perfect_time)}（积分完成率 {_pct(perfect_rate)}）。
第一梯队： {first_tier_str} 表现卓越，已提前超额完成时间进度目标。

三、 全光组网业务
整体情况： 端州累计发展 {_fmt_num(dz_total)} 户（目标 {QUANGUANG_DZ_TARGET} 户），完成率 {_pct(dz_rate)}；其中政企模块发展 {_fmt_num(qg_zhengqi)} 户，完成率 {_pct(qg_zhengqi_rate)}。
关键支撑： {qg_top_str} 率先实现规模突破。政企侧渗透率仍处于低位，需持续加强商机触达。

四、 三单协同获客
协同触达： 深化协同上门机制，打出共振组合拳，实现服务链和营销链的深度融合。
转化赋能： 优化要素配置，将聚焦客户触点、提升服务感知作为实现全业务融合发展的有力抓手，通过优质服务构建价值护城河，强化“高值引领，长尾穿透”的差异化服务矩阵。

五、 团队运营分析
团队对标： 大企业团队 综合表现相对稳健，高套完成率 {_pct(ent['gt_rate'])}（时间进度完成率 {_pct(ent['gt_time'])}），积分时间进度完成率 {_pct(ent['pf_time'])}（积分完成率 {_pct(ent['pf_rate'])}），且在全光组网贡献上稳步提升（完成率 {_pct(ent['qg_rate'])}）；党政军团队 高套完成率为 {_pct(party['gt_rate'])}（时间进度完成率 {_pct(party['gt_time'])}），积分时间进度完成率 {_pct(party['pf_time'])}（积分完成率 {_pct(party['pf_rate'])}）。面对新竞争态势，需主动破除路径依赖，强化商机挖掘，争取在新一轮范式转移中抢占核心生态位。
运营策略： 以深耕基本面夯实发展根基，通过专业赋能与经验复刻提升组织战斗力；将结果管理前移至过程经营，坚持前瞻谋划、布局先行、战略卡位，重视数据要素，深挖数据价值，统筹资源调配，以基础业务助推产数业务的高高质量发展。
逻辑闭环： 构建全周期运营体系，强化沟通联动，扩大朋友圈，以高效数据支撑决策，确保存量经营颗粒归仓，增量业务质效双增。"""

    return text


if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "runtime", "output", "*.xlsx")))
    if files:
        print(build_report_text(files[-1]))
    else:
        print("无结果 Excel，请先运行 server.py --local")
