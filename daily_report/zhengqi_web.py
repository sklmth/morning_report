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
LATEST_ROWS_V2 = os.path.join(INPUT_DIR, "latest_rows_v2.json")
OUTPUT_XLSX = os.path.join(OUTPUT_DIR, "家庭专项走访统计.xlsx")
OUTPUT_XLSX_V2 = os.path.join(OUTPUT_DIR, "家庭专项走访统计_V2.xlsx")


def _version_paths(version):
    if version == "v2":
        return LATEST_ROWS_V2, OUTPUT_XLSX_V2
    return LATEST_ROWS, OUTPUT_XLSX


def _ensure_dirs():
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _cleanup_archives(prefix_exts):
    """删除 INPUT_DIR 下旧的带时间戳归档，每类只保留最新 1 个。"""
    latest_files = {"latest.xlsx", "latest_rows.json", "latest_rows_v2.json"}
    for ext in prefix_exts:
        candidates = [
            f for f in os.listdir(INPUT_DIR)
            if f not in latest_files
            and f.endswith(ext)
            and len(f) >= 15
            and f[:8].isdigit()
        ]
        candidates.sort()
        for old in candidates[:-1]:  # 保留最新 1 个，删除其余
            try:
                os.remove(os.path.join(INPUT_DIR, old))
            except OSError:
                pass


def save_input(data, original_name=None):
    """保存推送来的原始 Excel 字节。

    写入 latest.xlsx（覆盖），同时按时间戳存一份归档（只保留最新 1 个）。
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
        pass
    _cleanup_archives([".xlsx"])
    return LATEST_INPUT


def save_rows(rows, original_name=None, version="v1"):
    """保存 AirScript / 金山文档脚本推送来的 JSON 行。"""
    _ensure_dirs()
    rows_path, _ = _version_paths(version)
    payload = json.dumps(rows, ensure_ascii=False)
    with open(rows_path, "w", encoding="utf-8") as f:
        f.write(payload)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = (original_name or "rows").replace(os.sep, "_")
    suffix = "_v2" if version == "v2" else ""
    archive = os.path.join(INPUT_DIR, f"{stamp}_{safe}{suffix}.json")
    try:
        with open(archive, "w", encoding="utf-8") as f:
            f.write(payload)
    except OSError:
        pass
    _cleanup_archives([".json"])
    return rows_path


def _newest_source(version="v1"):
    """返回指定版本中较新的 xlsx 或 JSON 行输入。"""
    rows_path, _ = _version_paths(version)
    xlsx_m = os.path.getmtime(LATEST_INPUT) if version == "v1" and os.path.exists(LATEST_INPUT) else None
    rows_m = os.path.getmtime(rows_path) if os.path.exists(rows_path) else None
    if xlsx_m is None and rows_m is None:
        return None
    if rows_m is None or (xlsx_m is not None and xlsx_m >= rows_m):
        return ("xlsx", LATEST_INPUT)
    return ("rows", rows_path)


def generate(ref_date=None, version="v1"):
    """基于指定版本的最新原始输入生成结果 Excel。"""
    src = _newest_source(version)
    if src is None:
        raise FileNotFoundError("尚未收到任何政企标准化信息收集表。")
    _ensure_dirs()
    kind, path = src
    _, output_path = _version_paths(version)
    if kind == "xlsx":
        from zhengqi_visit_stats import process_excel
        return process_excel(path, output_path, ref_date=ref_date)
    with open(path, "r", encoding="utf-8") as f:
        rows = json.load(f)
    if version == "v2":
        from zhengqi_visit_stats import process_rows_v2
        return process_rows_v2(rows, output_path, ref_date=ref_date)
    from zhengqi_visit_stats import process_rows
    return process_rows(rows, output_path, ref_date=ref_date)


def has_input(version="v1"):
    """是否已收到指定版本的输入。"""
    return _newest_source(version) is not None


def last_received(version="v1"):
    """指定版本最新原始输入的接收时间（datetime），无则 None。"""
    src = _newest_source(version)
    if src is None:
        return None
    return datetime.fromtimestamp(os.path.getmtime(src[1]))
