"""
营服业务通报表数据提取器
仅提取与14个政企客户经理相关的数据：
  - 071人员统计：激励金额（col16）、激励积分（col17）
  - 中心人员效能/下沉人员效能：揽装积分、高套、FTTR等
  - 016包区各指标汇总表：包区承包收入
"""

import re
from datetime import datetime
from typing import Optional
import pandas as pd

from analytics.config import NAMES


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
    m = re.search(r'(\d{8})', s)
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    m = re.search(r'(\d{1,2})月(\d{1,2})日', s)
    if m:
        mo, da = int(m.group(1)), int(m.group(2))
        year = datetime.today().year
        return f"{year}-{mo:02d}-{da:02d}"
    m = re.search(r'(\d{4}-\d{2}-\d{2})', s)
    if m:
        return m.group(1)
    return None


def extract_yingfu(file_path: str) -> dict:
    """
    解析营服业务通报表，返回仅包含14个政企客户经理的数据
    """
    result = {
        'data_date': None,
        'staff_efficiency': [],       # 14人效能（激励+业务指标）
        'staff_incentive_tier': [],    # 不再使用，保留空
        'cp_pair_metrics': [],         # 不再使用，保留空
        'area_contract_metrics': [],   # 包区数据
    }

    try:
        all_sheets = pd.read_excel(file_path, sheet_name=None, header=None)
    except Exception as e:
        raise RuntimeError(f"读取营服报表失败: {e}")

    names_set = set(NAMES)

    # ══════════════════════════════════════════════════════════════════════════
    # 071人员统计 — 14人激励金额（权威来源）
    # 表头: 行0-3为多级列头，数据从行4(iloc[4:])开始
    # col7=营业员名称(H列), col16=激励金额_计件(Q列), col17=激励积分_计件
    # ══════════════════════════════════════════════════════════════════════════
    incentive_map = {}  # {name: {'incentive': float, 'incentive_pts': float}}

    sheet_071 = "071人员统计"
    if sheet_071 in all_sheets:
        df = all_sheets[sheet_071]
        data_rows = df.iloc[4:].reset_index(drop=True)

        # 尝试从首个数据行读取日期
        if len(data_rows) > 0:
            date_val = _parse_date_from_cell(data_rows.iloc[0, 0])
            if date_val:
                result['data_date'] = date_val

        for _, row in data_rows.iterrows():
            name = str(row.iloc[7]).strip() if pd.notna(row.iloc[7]) else ""
            if name not in names_set:
                continue
            incentive_map[name] = {
                'incentive': _safe(row.iloc[16]) if len(row) > 16 else 0,
                'incentive_pts': _safe(row.iloc[17]) if len(row) > 17 else 0,
                'incentive_new': _safe(row.iloc[18]) if len(row) > 18 else 0,
                'incentive_stock': _safe(row.iloc[19]) if len(row) > 19 else 0,
            }

    # ══════════════════════════════════════════════════════════════════════════
    # 中心人员效能 / 下沉人员效能 — 揽装积分、高套、FTTR等业务指标
    # 表头: 行0标题，行1列名，数据从行2(iloc[2:])开始
    # col1=中心, col2=角色, col3=姓名, col4=预计激励(不用！), col5=综合高套
    # col6=高套, col7=存量高套, col8=揽装积分, col9=激励积分, col10=高套积分
    # col11=存量高套积分, col12=FTTR, col13=合约, col14=移动
    # ══════════════════════════════════════════════════════════════════════════
    eff_records = []
    for sheet_name in ["中心人员效能", "下沉人员效能"]:
        if sheet_name not in all_sheets:
            continue
        df = all_sheets[sheet_name]
        data_rows = df.iloc[2:].reset_index(drop=True)

        for _, row in data_rows.iterrows():
            name = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
            if name not in names_set:
                continue

            date_val = _parse_date_from_cell(row.iloc[0])
            if date_val and not result['data_date']:
                result['data_date'] = date_val

            # 激励从071人员统计取（权威来源），不从此表取
            inc_data = incentive_map.get(name, {})
            eff_records.append({
                'name': name,
                'center': str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else "政企",
                'role': str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else "",
                # 激励从071人员统计取
                'predicted_incentive': inc_data.get('incentive', 0),
                'total_gaotao': _safe(row.iloc[5]) if len(row) > 5 else 0,
                'new_gaotao': _safe(row.iloc[6]) if len(row) > 6 else 0,
                'stock_gaotao': _safe(row.iloc[7]) if len(row) > 7 else 0,
                'device_pts': _safe(row.iloc[8]) if len(row) > 8 else 0,
                'incentive_pts': inc_data.get('incentive_pts', 0),
                'gaotao_pts': _safe(row.iloc[10]) if len(row) > 10 else 0,
                'stock_gaotao_pts': _safe(row.iloc[11]) if len(row) > 11 else 0,
                'fttr': int(_safe(row.iloc[12])) if len(row) > 12 else 0,
                'contract': int(_safe(row.iloc[13])) if len(row) > 13 else 0,
                'mobile': int(_safe(row.iloc[14])) if len(row) > 14 else 0,
            })

    # 如果14人中有人在071人员统计中有数据但不在"中心人员效能"里
    # 补充一条仅含激励的记录
    eff_names = {r['name'] for r in eff_records}
    for name, inc_data in incentive_map.items():
        if name not in eff_names:
            eff_records.append({
                'name': name,
                'center': '政企',
                'role': '客户经理',
                'predicted_incentive': inc_data.get('incentive', 0),
                'total_gaotao': 0,
                'new_gaotao': 0,
                'stock_gaotao': 0,
                'device_pts': 0,
                'incentive_pts': inc_data.get('incentive_pts', 0),
                'gaotao_pts': 0,
                'stock_gaotao_pts': 0,
                'fttr': 0,
                'contract': 0,
                'mobile': 0,
            })

    result['staff_efficiency'] = eff_records

    # ══════════════════════════════════════════════════════════════════════════
    # 016-包区各指标汇总表 — 包区承包收入
    # ══════════════════════════════════════════════════════════════════════════
    sheet_area = "016-包区各指标汇总表"
    if sheet_area in all_sheets:
        df = all_sheets[sheet_area]
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
            })
            if date_val and not result['data_date']:
                result['data_date'] = date_val
        result['area_contract_metrics'] = records

    # 兜底日期
    if not result['data_date']:
        result['data_date'] = datetime.today().strftime('%Y-%m-%d')

    return result
