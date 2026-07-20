"""政企家庭专项走访统计 —— Web 层薄封装。

职责：
    - 保存金山文档脚本推送来的原始 Excel（latest + 时间戳存档）
    - 调用 zhengqi_visit_stats.process_excel 生成统计结果 Excel
    - 提供「下载最新结果」所需的路径解析

与 web_server 解耦：web_server 只调这里的 3 个函数。

"今周"口径是动态的（按当天自然周），因此下载时**基于最新原始表重新生成**，
保证下周下载得到下周口径，而不是沿用旧结果。
"""

import json
import os
import sys
from datetime import datetime

# 让 zhengqi_visit_stats 包（位于项目根目录）可被导入
_SRC = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SRC)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# runtime 目录布局
_BASE = os.path.join(_ROOT, "runtime", "zhengqi")
INPUT_DIR = os.path.join(_BASE, "input")
OUTPUT_DIR = os.path.join(_BASE, "output")
LATEST_INPUT = os.path.join(INPUT_DIR, "latest.xlsx")
LATEST_ROWS = os.path.join(INPUT_DIR, "latest_rows.json")  # AirScript JSON 行推送
OUTPUT_XLSX = os.path.join(OUTPUT_DIR, "家庭专项走访统计.xlsx")


def _ensure_dirs():
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_input(data, original_name=None):
    """保存推送来的原始 Excel 字节。

    写入 latest.xlsx（覆盖），同时按时间戳存一份归档，便于回溯。
    返回 latest.xlsx 路径。
    """
    _ensure_dirs()
    with open(LATEST_INPUT, "wb") as f:
        f.write(data)
    # 归档
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = (original_name or "input.xlsx").replace(os.sep, "_")
    archive = os.path.join(INPUT_DIR, f"{stamp}_{safe}")
    try:
        with open(archive, "wb") as f:
            f.write(data)
    except OSError:
        pass  # 归档失败不影响主流程
    return LATEST_INPUT


def save_rows(rows, original_name=None):
    """保存 AirScript / 金山文档脚本推送来的 JSON 行。

    写入 latest_rows.json（覆盖），同时按时间戳存一份归档。
    返回 latest_rows.json 路径。
    """
    _ensure_dirs()
    payload = json.dumps(rows, ensure_ascii=False)
    with open(LATEST_ROWS, "w", encoding="utf-8") as f:
        f.write(payload)
    # 归档
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = (original_name or "rows").replace(os.sep, "_")
    archive = os.path.join(INPUT_DIR, f"{stamp}_{safe}.json")
    try:
        with open(archive, "w", encoding="utf-8") as f:
            f.write(payload)
    except OSError:
        pass  # 归档失败不影响主流程
    return LATEST_ROWS


def _newest_source():
    """返回两种输入源中较新的一个：("xlsx", path) / ("rows", path) / None。"""
    xlsx_m = os.path.getmtime(LATEST_INPUT) if os.path.exists(LATEST_INPUT) else None
    rows_m = os.path.getmtime(LATEST_ROWS) if os.path.exists(LATEST_ROWS) else None
    if xlsx_m is None and rows_m is None:
        return None
    if rows_m is None or (xlsx_m is not None and xlsx_m >= rows_m):
        return ("xlsx", LATEST_INPUT)
    return ("rows", LATEST_ROWS)


def generate(ref_date=None):
    """基于最新原始输入（xlsx 或 JSON 行，取较新者）生成结果 Excel。

    返回 (df, out_path)。若尚无任何输入，抛 FileNotFoundError。
    """
    src = _newest_source()
    if src is None:
        raise FileNotFoundError("尚未收到任何政企标准化信息收集表。")
    _ensure_dirs()
    kind, path = src
    if kind == "xlsx":
        from zhengqi_visit_stats import process_excel
        return process_excel(path, OUTPUT_XLSX, ref_date=ref_date)
    # JSON 行
    from zhengqi_visit_stats import process_rows
    with open(path, "r", encoding="utf-8") as f:
        rows = json.load(f)
    return process_rows(rows, OUTPUT_XLSX, ref_date=ref_date)


def has_input():
    """是否已收到过任一来源的原始输入。"""
    return _newest_source() is not None


def last_received():
    """最新原始输入的接收时间（datetime），无则 None。"""
    src = _newest_source()
    if src is None:
        return None
    return datetime.fromtimestamp(os.path.getmtime(src[1]))
