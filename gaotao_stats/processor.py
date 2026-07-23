"""营服报表 —— 客户经理新增/存量高套清单核心逻辑。

数据源：营服报表（业务通报），pd.read_excel(..., header=None) 读取。

③高套清单（新增高套）  列索引（0-based）：
    N  接入号     -> 13
    AM 客户经理   -> 38
    I  竣工日期   -> 8
    BL 积分       -> 63
    BR 高套数     -> 69

④存量高套清单（存量高套）列索引（0-based）：
    E  接入号     -> 4
    BX 客户经理   -> 75
    CU 竣工时间   -> 98
    AK 积分       -> 36
    CS 高套系数   -> 96（作为高套数）

客户经理名单沿用「早会五张表」定义（daily_report.function.names）。
仅保留名单内客户经理的记录。
"""

import os

import pandas as pd

# 客户经理名单（与 daily_report/function.py 的 names 保持一致）
NAMES = [
    "麦海芬", "黄淡妮", "邱海燕", "李东",
    "王锦添", "黄观霞", "谢卓和", "伍颖敏",
    "李玉强", "张小敏", "具进康", "邓天群", 
]

# sheet 名 -> 列映射（接入号 / 客户经理 / 竣工日期 / 积分 / 高套数）
NEW_SHEET_SUFFIX = "高套清单"
STOCK_SHEET_SUFFIX = "存量高套清单"

# ③高套清单：接入号 N=13, 客户经理 AM=38, 竣工日期 I=8, 积分 BL=63, 高套数 BR=69
NEW_COLS = {"接入号": 13, "客户经理": 38, "竣工日期": 8, "积分": 63, "高套数": 69}
# ④存量高套清单：接入号 E=4, 客户经理 BX=75, 竣工时间 CU=98, 积分 AK=36, 高套系数 CS=96
STOCK_COLS = {"接入号": 4, "客户经理": 75, "竣工日期": 98, "积分": 36, "高套数": 96}

HEADERS = ["接入号", "客户经理", "竣工日期", "积分", "高套数"]


def _find_sheet(data, suffix, exclude_suffix=None):
    """按后缀匹配 sheet 名，兼容带/不带序号前缀（如 ③高套清单）。

    exclude_suffix 用于让「高套清单」不误命中「存量高套清单」。
    """
    for s in data:
        if exclude_suffix and s.endswith(exclude_suffix):
            continue
        if s == suffix or s.endswith(suffix):
            return s
    return None


def _fmt_date(val):
    """竣工日期规整为 YYYY-MM-DD 字符串；无法解析则原样返回。

    兼容三种来源格式：
    - pandas Timestamp / Python datetime（read_excel 自动转换的日期单元格）
    - 整数 20260721 形式（YYYYMMDD 数字）
    - Excel 序列日期（整数，距 1899-12-30 的天数）
    """
    import datetime as _dt

    if pd.isna(val):
        return ""

    # 已经是 datetime / Timestamp
    if isinstance(val, (pd.Timestamp, _dt.datetime, _dt.date)):
        return pd.Timestamp(val).strftime("%Y-%m-%d")

    # 数值：优先尝试 YYYYMMDD 整数格式，次选 Excel 序列日期
    if isinstance(val, (int, float)):
        s = str(int(val))
        if len(s) == 8:           # YYYYMMDD
            dt = pd.to_datetime(s, format="%Y%m%d", errors="coerce")
            if not pd.isna(dt):
                return dt.strftime("%Y-%m-%d")
        # Excel 序列日期（距 1899-12-30 天数）
        try:
            dt = pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(val))
            if 1900 <= dt.year <= 2100:
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # 字符串兜底
    dt = pd.to_datetime(str(val).strip(), errors="coerce")
    if not pd.isna(dt):
        return dt.strftime("%Y-%m-%d")
    return str(val).strip()


def _extract(data, sheet_name, cols):
    """从指定 sheet 提取明细，返回列为 HEADERS 的 DataFrame，仅保留名单内客户经理。"""
    df = data[sheet_name]
    idx = [cols[h] for h in HEADERS]
    # 首行为表头，从第 2 行起取数据
    t = df.iloc[1:, idx].copy()
    t.columns = HEADERS
    t["客户经理"] = t["客户经理"].astype(str).str.strip()
    t = t[t["客户经理"].isin(NAMES)].copy()

    t["接入号"] = t["接入号"].apply(lambda v: "" if pd.isna(v) else str(v).strip())
    t["竣工日期"] = t["竣工日期"].apply(_fmt_date)
    t["积分"] = pd.to_numeric(t["积分"], errors="coerce").fillna(0)
    t["高套数"] = pd.to_numeric(t["高套数"], errors="coerce").fillna(0)

    # 按名单顺序、客户经理分组排序，便于阅读
    order = {n: i for i, n in enumerate(NAMES)}
    t["_o"] = t["客户经理"].map(order)
    t = t.sort_values(["_o", "竣工日期"], kind="stable").drop(columns="_o").reset_index(drop=True)
    return t[HEADERS]


def compute_tables(input_path):
    """读取营服报表，返回 (新增高套 df, 存量高套 df)。"""
    data = pd.read_excel(input_path, sheet_name=None, header=None)

    new_sheet = _find_sheet(data, NEW_SHEET_SUFFIX, exclude_suffix=STOCK_SHEET_SUFFIX)
    stock_sheet = _find_sheet(data, STOCK_SHEET_SUFFIX)

    if new_sheet is None:
        raise ValueError(f"营服报表缺少「{NEW_SHEET_SUFFIX}」sheet，实际：{list(data.keys())}")
    if stock_sheet is None:
        raise ValueError(f"营服报表缺少「{STOCK_SHEET_SUFFIX}」sheet，实际：{list(data.keys())}")

    df_new = _extract(data, new_sheet, NEW_COLS)
    df_stock = _extract(data, stock_sheet, STOCK_COLS)
    return df_new, df_stock


def process_excel(input_path, out_path=None):
    """主接口：输入营服报表，输出含两 sheet 的高套清单 Excel。

    返回 (df_new, df_stock, out_path)。
    """
    df_new, df_stock = compute_tables(input_path)

    if out_path is None:
        base = os.path.splitext(os.path.basename(input_path))[0]
        out_path = os.path.join(
            os.path.dirname(os.path.abspath(input_path)),
            f"{base}_客户经理高套清单.xlsx",
        )

    from .styling import write_styled_workbook
    write_styled_workbook(df_new, df_stock, out_path)
    return df_new, df_stock, out_path
