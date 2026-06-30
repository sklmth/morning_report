"""
营服业务通报表数据提取器
从营服Excel中提取人员效能、CP对、包区承包、激励档位等数据
"""

import re
from datetime import datetime
from typing import Optional
import pandas as pd

from analytics.config import ALL_STAFF_NAMES


def _safe(val, default=0.0):
    if val is None:
        return default
    try:
        f = float(val)
        return default if (f != f) else f
    except (TypeError, ValueError):
        return default


def _parse_date_from_cell(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    # 20260628
    m = re.search(r'(\d{8})', s)
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    # 6月28日 → 用当前年份
    m = re.search(r'(\d{1,2})月(\d{1,2})日', s)
    if m:
        mo, da = int(m.group(1)), int(m.group(2))
        year = datetime.today().year
        return f"{year}-{mo:02d}-{da:02d}"
    # 2026-06-28
    m = re.search(r'(\d{4}-\d{2}-\d{2})', s)
    if m:
        return m.group(1)
    return None


def extract_yingfu(file_path: str) -> dict:
    """
    解析营服业务通报表，返回：
    {
        'data_date': str,
        'staff_efficiency': [dict, ...],
        'staff_incentive_tier': [dict, ...],
        'cp_pair_metrics': [dict, ...],
        'area_contract_metrics': [dict, ...],
    }
    """
    result = {
        'data_date': None,
        'staff_efficiency': [],
        'staff_incentive_tier': [],
        'cp_pair_metrics': [],
        'area_contract_metrics': [],
    }

    try:
        all_sheets = pd.read_excel(file_path, sheet_name=None, header=None)
    except Exception as e:
        raise RuntimeError(f"读取营服报表失败: {e}")

    # ── 中心人员效能 ─────────────────────────────────────────────────────────
    sheet_eff = "中心人员效能"
    if sheet_eff in all_sheets:
        df = all_sheets[sheet_eff]
        # 第1行标题，第2行列名，数据从第3行(index=2)开始
        data_rows = df.iloc[2:].reset_index(drop=True)

        # 解析日期（第2行第0列可能有日期）
        date_str = _parse_date_from_cell(df.iloc[2, 0] if len(df) > 2 else None)
        if date_str:
            result['data_date'] = date_str

        records = []
        for _, row in data_rows.iterrows():
            name = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
            if not name or name in ("nan", "人员"):
                continue
            date_val = _parse_date_from_cell(row.iloc[0])
            records.append({
                'name': name,
                'center': str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else "",
                'role': str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else "",
                'predicted_incentive': _safe(row.iloc[4]) if len(row) > 4 else 0,
                'total_gaotao': _safe(row.iloc[5]) if len(row) > 5 else 0,
                'new_gaotao': _safe(row.iloc[6]) if len(row) > 6 else 0,
                'stock_gaotao': _safe(row.iloc[7]) if len(row) > 7 else 0,
                'device_pts': _safe(row.iloc[8]) if len(row) > 8 else 0,
                'incentive_pts': _safe(row.iloc[9]) if len(row) > 9 else 0,
                'gaotao_pts': _safe(row.iloc[10]) if len(row) > 10 else 0,
                'stock_gaotao_pts': _safe(row.iloc[11]) if len(row) > 11 else 0,
                'fttr': int(_safe(row.iloc[12])) if len(row) > 12 else 0,
                'contract': int(_safe(row.iloc[13])) if len(row) > 13 else 0,
                'mobile': int(_safe(row.iloc[14])) if len(row) > 14 else 0,
                '_date_override': date_val,  # 行内日期，优先用
            })
        # 若行内日期存在，取第一个非空的
        if records:
            for r in records:
                d = r.pop('_date_override', None)
                if d and not result['data_date']:
                    result['data_date'] = d
        result['staff_efficiency'] = records

    # ── 下沉人员效能（同格式）────────────────────────────────────────────────
    sheet_sink = "下沉人员效能"
    if sheet_sink in all_sheets:
        df = all_sheets[sheet_sink]
        data_rows = df.iloc[2:].reset_index(drop=True)
        records = []
        for _, row in data_rows.iterrows():
            name = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
            if not name or name in ("nan", "人员"):
                continue
            date_val = _parse_date_from_cell(row.iloc[0])
            records.append({
                'name': name,
                'center': str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else "",
                'role': str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else "",
                'predicted_incentive': _safe(row.iloc[4]) if len(row) > 4 else 0,
                'total_gaotao': _safe(row.iloc[5]) if len(row) > 5 else 0,
                'new_gaotao': _safe(row.iloc[6]) if len(row) > 6 else 0,
                'stock_gaotao': _safe(row.iloc[7]) if len(row) > 7 else 0,
                'device_pts': _safe(row.iloc[8]) if len(row) > 8 else 0,
                'incentive_pts': _safe(row.iloc[9]) if len(row) > 9 else 0,
                'gaotao_pts': _safe(row.iloc[10]) if len(row) > 10 else 0,
                'stock_gaotao_pts': _safe(row.iloc[11]) if len(row) > 11 else 0,
                'fttr': int(_safe(row.iloc[12])) if len(row) > 12 else 0,
                'contract': int(_safe(row.iloc[13])) if len(row) > 13 else 0,
                'mobile': int(_safe(row.iloc[14])) if len(row) > 14 else 0,
            })
        # 合并到 staff_efficiency
        result['staff_efficiency'].extend(records)

    # ── 中心人员预计酬金（激励档位）────────────────────────────────────────────
    sheet_tier = "中心人员预计酬金"
    if sheet_tier in all_sheets:
        df = all_sheets[sheet_tier]
        # 第1行是列头，数据从第2行(index=1)开始
        data_rows = df.iloc[1:].reset_index(drop=True)

        records = []
        for _, row in data_rows.iterrows():
            name = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
            if not name or name in ("nan",):
                continue
            date_val = _parse_date_from_cell(row.iloc[0])
            records.append({
                'name': name,
                'center': str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else "",
                'cp_group': str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else "",
                'device_pts': _safe(row.iloc[4]) if len(row) > 4 else 0,
                'tier_129_pts': _safe(row.iloc[5]) if len(row) > 5 else 0,
                'tier_169_pts': _safe(row.iloc[6]) if len(row) > 6 else 0,
                'tier_199_pts': _safe(row.iloc[7]) if len(row) > 7 else 0,
                'bastion_托收_low': _safe(row.iloc[8]) if len(row) > 8 else 0,
                'bastion_托收_high': _safe(row.iloc[9]) if len(row) > 9 else 0,
                'bastion_非托收_low': _safe(row.iloc[10]) if len(row) > 10 else 0,
                'bastion_非托收_high': _safe(row.iloc[11]) if len(row) > 11 else 0,
                'pure_new_pts': _safe(row.iloc[12]) if len(row) > 12 else 0,
                'stock_non_bastion_pts': _safe(row.iloc[13]) if len(row) > 13 else 0,
                'dev_incentive': _safe(row.iloc[14]) if len(row) > 14 else 0,
                '_date_override': date_val,
            })
        if records:
            for r in records:
                d = r.pop('_date_override', None)
                if d and not result['data_date']:
                    result['data_date'] = d
        result['staff_incentive_tier'] = records

    # ── 服务工资计算（CP对）─────────────────────────────────────────────────
    sheet_cp = "服务工资计算"
    if sheet_cp in all_sheets:
        df = all_sheets[sheet_cp]
        # 第1行是列头，数据从第2行(index=1)开始
        data_rows = df.iloc[1:].reset_index(drop=True)

        records = []
        for _, row in data_rows.iterrows():
            center = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            if not center or center in ("nan",):
                continue
            records.append({
                'center': center,
                'cp_group': str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else "",
                'sales_name': str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else "",
                'install_name': str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else "",
                'cp_target': _safe(row.iloc[4]) if len(row) > 4 else 0,
                'sales_target': _safe(row.iloc[5]) if len(row) > 5 else 0,
                'install_target': _safe(row.iloc[6]) if len(row) > 6 else 0,
                'sales_pts_actual': _safe(row.iloc[7]) if len(row) > 7 else 0,
                'install_pts_actual': _safe(row.iloc[8]) if len(row) > 8 else 0,
                'cp_pts_total': _safe(row.iloc[9]) if len(row) > 9 else 0,
                'sales_service_wage': _safe(row.iloc[10]) if len(row) > 10 else 0,
                'install_coeff': _safe(row.iloc[11]) if len(row) > 11 else 0,
                'install_gap': _safe(row.iloc[12]) if len(row) > 12 else 0,
                'cp_gap': _safe(row.iloc[13]) if len(row) > 13 else 0,
            })
        result['cp_pair_metrics'] = records

    # ── 016-包区各指标汇总表 ──────────────────────────────────────────────────
    sheet_area = "016-包区各指标汇总表"
    if sheet_area in all_sheets:
        df = all_sheets[sheet_area]
        # 前3行是多级列头，数据从第4行(index=3)开始
        data_rows = df.iloc[3:].reset_index(drop=True)

        records = []
        for _, row in data_rows.iterrows():
            area_name_raw = row.iloc[4] if len(row) > 4 else None
            area_name = str(area_name_raw).strip() if pd.notna(area_name_raw) else ""
            if not area_name or area_name in ("nan",):
                continue
            date_val = _parse_date_from_cell(row.iloc[0])
            records.append({
                'area_id': str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else "",
                'area_name': area_name,
                'center': str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else "",
                'area_type': str(row.iloc[7]).strip() if len(row) > 7 and pd.notna(row.iloc[7]) else "",
                'contractor': str(row.iloc[9]).strip() if len(row) > 9 and pd.notna(row.iloc[9]) else "",
                'income_target': _safe(row.iloc[17]) if len(row) > 17 else 0,
                'income_actual': _safe(row.iloc[18]) if len(row) > 18 else 0,
                'income_yoy': _safe(row.iloc[19]) if len(row) > 19 else 0,
                'income_mom': _safe(row.iloc[20]) if len(row) > 20 else 0,
                'income_cum': _safe(row.iloc[21]) if len(row) > 21 else 0,
                'time_progress': _safe(row.iloc[23]) if len(row) > 23 else 0,
                'cum_progress': _safe(row.iloc[24]) if len(row) > 24 else 0,
                'pts_target': _safe(row.iloc[25]) if len(row) > 25 else 0,
                'pts_actual': _safe(row.iloc[26]) if len(row) > 26 else 0,
                '_date_override': date_val,
            })
        if records:
            for r in records:
                d = r.pop('_date_override', None)
                if d and not result['data_date']:
                    result['data_date'] = d
        result['area_contract_metrics'] = records

    # 兜底日期
    if not result['data_date']:
        result['data_date'] = datetime.today().strftime('%Y-%m-%d')

    return result
