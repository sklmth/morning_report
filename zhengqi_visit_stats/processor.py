"""政企标准化信息收集 —— 家庭专项走访统计核心逻辑。

统计口径
--------
数据源：政企标准化信息收集 Excel（表格视图导出）。
关键列（按表头名匹配，避免列位置漂移）：
    E  填写人员姓名           -> 客户经理
    G  拜访对象类型           -> 仅统计「企业员工-进企业做家庭专项」
    T  拜访结果（上门后回填） -> 值为「已拜访」计入走访数

每个客户经理指标：
    今周目标   = 5（固定）
    预约数     = 该经理满足 G 列口径的记录条数
    走访数     = 其中 T 列为「已拜访」的条数
    预约完成率 = 预约数 / 5        （重点指标，< 5 户标红）
    走访完成率 = 走访数 / 5
    差值       = 5 - 预约数        （还差多少户达标）
"""

import os
from datetime import date, datetime, timedelta

import pandas as pd

# G 列筛选口径
VISIT_TYPE = "企业员工-进企业做家庭专项"
# T 列「已拜访」判定
VISITED_FLAG = "已拜访"
# 今周目标（固定 5 户）
WEEKLY_TARGET = 5

# 固定客户经理名单：无数据者按预约数 0 统计。
# 邓天群在实习期，暂不统计，故不在名单内。
ROSTER = [
    "麦海芬", "黄淡妮", "邱海燕", "李东", "王锦添", "黄观霞",
    "谢卓和", "伍颖敏", "李玉强", "张小敏", "具进康",
]
# 实习期（不统计）
EXCLUDED = {"邓天群"}

# 表头名 -> 逻辑字段（按名匹配，容忍列顺序变化）
_COL_NAME = "填写人员姓名"
_COL_TYPE = "拜访对象类型"
_COL_RESULT = "拜访结果（上门后回填）"
_COL_APPT_DATE = "预约上门日期"  # K 列，作为「今周」判定依据


def week_range(ref=None):
    """返回 ref 所在自然周的 (周一, 周日) date。ref 默认今天。

    周口径动态：本周统计本周，下周自动切到下周。
    """
    if ref is None:
        ref = date.today()
    elif isinstance(ref, datetime):
        ref = ref.date()
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _locate_columns(df):
    """按表头名定位所需列，返回 (name_col, type_col, result_col) 的实际列名。

    表头可能带前后空格或换行，做一次归一化匹配。
    """
    norm = {str(c).strip().replace("\n", ""): c for c in df.columns}

    def pick(target):
        if target in norm:
            return norm[target]
        # 退化匹配：去掉括号差异后包含关系
        for k, orig in norm.items():
            if target[:4] in k:
                return orig
        raise KeyError(f"输入表缺少列「{target}」，实际列：{list(df.columns)}")

    return pick(_COL_NAME), pick(_COL_TYPE), pick(_COL_RESULT), pick(_COL_APPT_DATE)


def compute_stats(input_path, sheet_name=0, ref_date=None):
    """读取输入 Excel，按口径统计，返回结果 DataFrame（不含样式）。

    列：客户经理 / 今周目标 / 预约数 / 走访数 / 预约完成率 / 走访完成率 / 差值
    末行为「合计」。

    今周口径：按 K 列「预约上门日期」落在 ref_date 所在自然周（周一~周日）内。
    ref_date 默认今天，动态跟随当前周。
    """
    df = pd.read_excel(input_path, sheet_name=sheet_name)
    return compute_stats_from_df(df, ref_date=ref_date)


def compute_stats_from_rows(rows, ref_date=None):
    """从 JSON 行统计（AirScript / 金山文档脚本推送用）。

    rows 为 dict 列表，每条至少包含以下逻辑键（缺失按空处理）：
        name       -> 填写人员姓名
        type       -> 拜访对象类型
        appt_date  -> 预约上门日期（字符串，如 "2026-07-15"）
        result     -> 拜访结果（上门后回填）
    也兼容直接用中文表头名作为键。

    构造成与 Excel 同构的 DataFrame 后复用 compute_stats_from_df，
    保证与文件上传口径完全一致。
    """
    def g(r, logical, cn):
        if logical in r:
            return r[logical]
        return r.get(cn, "")

    df = pd.DataFrame([{
        _COL_NAME: g(r, "name", _COL_NAME),
        _COL_TYPE: g(r, "type", _COL_TYPE),
        _COL_APPT_DATE: g(r, "appt_date", _COL_APPT_DATE),
        _COL_RESULT: g(r, "result", _COL_RESULT),
    } for r in (rows or [])], columns=[
        _COL_NAME, _COL_TYPE, _COL_APPT_DATE, _COL_RESULT,
    ])
    return compute_stats_from_df(df, ref_date=ref_date)


def compute_stats_from_df(df, ref_date=None):
    """核心统计：输入已含所需列的 DataFrame，返回结果 DataFrame。

    Excel 上传与 JSON 行上传共用此函数，确保口径一致。
    """
    name_col, type_col, result_col, appt_date_col = _locate_columns(df)

    monday, sunday = week_range(ref_date)

    # 仅家庭专项口径
    sub = df[df[type_col].astype(str).str.strip() == VISIT_TYPE].copy()

    # 今周口径：K 列预约上门日期在 [周一, 周日] 内
    appt_dt = pd.to_datetime(sub[appt_date_col], errors="coerce").dt.date
    in_week = appt_dt.between(monday, sunday)
    sub = sub[in_week].copy()

    # 按经理聚合出预约数/走访数
    counts = {}  # name -> (预约数, 走访数)
    if not sub.empty:
        sub["_name"] = sub[name_col].astype(str).str.strip()
        sub["_visited"] = sub[result_col].astype(str).str.strip() == VISITED_FLAG
        for name, g in sub.groupby("_name", sort=False):
            counts[name] = (int(len(g)), int(g["_visited"].sum()))

    # 以固定名单为准：名单内无数据 -> 预约数 0；名单外/实习期不统计
    rows = []
    for name in ROSTER:
        if name in EXCLUDED:
            continue
        appt, visited = counts.get(name, (0, 0))
        rows.append({
            "客户经理": name,
            "今周目标": WEEKLY_TARGET,
            "预约数": appt,
            "走访数": visited,
            "预约完成率": appt / WEEKLY_TARGET,
            "走访完成率": visited / WEEKLY_TARGET,
            "差值": WEEKLY_TARGET - appt,
        })

    result = pd.DataFrame(rows, columns=[
        "客户经理", "今周目标", "预约数", "走访数",
        "预约完成率", "走访完成率", "差值",
    ])

    # 按差值降序排列（差值越大越靠前；并列时走访数降序）
    if not result.empty:
        result = result.sort_values(
            ["差值", "走访数"], ascending=[False, False],
            kind="stable",
        ).reset_index(drop=True)

    # 合计行
    if not result.empty:
        total_appt = int(result["预约数"].sum())
        total_visited = int(result["走访数"].sum())
        total_target = WEEKLY_TARGET * len(result)
        total = {
            "客户经理": "合计",
            "今周目标": total_target,
            "预约数": total_appt,
            "走访数": total_visited,
            "预约完成率": (total_appt / total_target) if total_target else 0,
            "走访完成率": (total_visited / total_target) if total_target else 0,
            "差值": total_target - total_appt,
        }
        result = pd.concat([result, pd.DataFrame([total])], ignore_index=True)

    return result


def process_excel(input_path, out_path=None, sheet_name=0, ref_date=None):
    """主接口：输入政企标准化信息收集 Excel，输出统计结果 Excel。

    参数：
        input_path : 源 Excel 路径
        out_path   : 结果 Excel 路径；None 时在源文件同目录生成
        sheet_name : 源 sheet（默认第一个）
        ref_date   : 参考日期，决定"今周"区间；默认今天
    返回：
        (result_df, out_path)
    """
    result = compute_stats(input_path, sheet_name=sheet_name, ref_date=ref_date)
    monday, sunday = week_range(ref_date)

    if out_path is None:
        base = os.path.splitext(os.path.basename(input_path))[0]
        out_path = os.path.join(
            os.path.dirname(os.path.abspath(input_path)),
            f"{base}_家庭专项走访统计.xlsx",
        )

    # 延迟导入，避免无样式需求时的开销
    from .styling import write_styled_table
    title = (f"政企家庭专项走访统计"
             f"（{monday:%m.%d}-{sunday:%m.%d} 今周目标 {WEEKLY_TARGET} 户/人）")
    write_styled_table(result, out_path, title=title)
    return result, out_path


def process_rows(rows, out_path, ref_date=None):
    """主接口（JSON 行版）：输入行数据，输出统计结果 Excel。

    参数：
        rows     : dict 列表，见 compute_stats_from_rows
        out_path : 结果 Excel 路径（必填）
        ref_date : 参考日期，决定"今周"区间；默认今天
    返回：
        (result_df, out_path)
    """
    result = compute_stats_from_rows(rows, ref_date=ref_date)
    monday, sunday = week_range(ref_date)

    from .styling import write_styled_table
    title = (f"政企家庭专项走访统计"
             f"（{monday:%m.%d}-{sunday:%m.%d} 今周目标 {WEEKLY_TARGET} 户/人）")
    write_styled_table(result, out_path, title=title)
    return result, out_path
