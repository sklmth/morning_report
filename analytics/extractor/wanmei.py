"""
完美一单报表数据提取器
从完美一单Excel中提取完整的多维度数据，存入analytics.db
"""

import os
import re
from datetime import datetime
from typing import Optional
import pandas as pd
import openpyxl

from analytics.config import BRANCH_NAMES, DUANZHOU_DISTRICT_ALIASES


def _safe(val, default=0.0):
    """安全转换为float，处理None/NaN/错误值"""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (f != f) else f  # NaN check
    except (TypeError, ValueError):
        return default


def _parse_data_date(ws_row1_val) -> Optional[str]:
    """从sheet首行或数据行解析日期，返回 'YYYY-MM-DD' 格式"""
    if ws_row1_val is None:
        return None
    s = str(ws_row1_val).strip()
    # 格式 20260628
    m = re.search(r'(\d{8})', s)
    if m:
        d = m.group(1)
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    # 格式 2026-06-28
    m = re.search(r'(\d{4}-\d{2}-\d{2})', s)
    if m:
        return m.group(1)
    return None


def extract_wanmei(file_path: str) -> dict:
    """
    解析完美一单报表Excel，返回结构化数据字典：
    {
        'data_date': str,
        'person_monthly': [dict, ...],
        'person_daily': [dict, ...],
        'district_monthly': [dict, ...],
        'district_daily': [dict, ...],
        'outlet_monthly': [dict, ...],
    }
    """
    result = {
        'data_date': None,
        'person_monthly': [],
        'person_daily': [],
        'district_monthly': [],
        'district_daily': [],
        'outlet_monthly': [],
    }

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    sheet_names = wb.sheetnames
    wb.close()

    # 读取所有sheet（pandas一次性加载）
    try:
        all_sheets = pd.read_excel(file_path, sheet_name=None, header=None)
    except Exception as e:
        raise RuntimeError(f"读取完美一单失败: {e}")

    # ── 揽装人维度（月累）─────────────────────────────────────────────────────
    sheet_name_month = "揽装人维度（月累)"
    if sheet_name_month in all_sheets:
        df = all_sheets[sheet_name_month]
        # 前5行是表头，从第6行开始是数据
        data_rows = df.iloc[5:].reset_index(drop=True)

        # 从第1行尝试解析日期
        date_str = _parse_data_date(df.iloc[0, 0])
        if date_str:
            result['data_date'] = date_str

        records = []
        for _, row in data_rows.iterrows():
            name = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""
            if not name or name in ("nan", "客户经理名称"):
                continue
            records.append({
                'name': name,
                'district': str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else "",
                'team': str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else "",
                # 高套
                'new_gaotao': _safe(row.iloc[5]),
                'stock_gaotao': _safe(row.iloc[6]),
                'new_gaotao_zq': _safe(row.iloc[7]),
                'stock_gaotao_zq': _safe(row.iloc[8]),
                # 双线高套
                'new_gaotao_twin': _safe(row.iloc[9]) if len(row) > 9 else 0,
                'stock_gaotao_twin': _safe(row.iloc[10]) if len(row) > 10 else 0,
                # 增量积分
                'inc_pts_total': _safe(row.iloc[13]) if len(row) > 13 else 0,
                'inc_pts_base': _safe(row.iloc[14]) if len(row) > 14 else 0,
                'inc_pts_mobile': _safe(row.iloc[15]) if len(row) > 15 else 0,
                'inc_pts_bb': _safe(row.iloc[16]) if len(row) > 16 else 0,
                'inc_pts_phone': _safe(row.iloc[17]) if len(row) > 17 else 0,
                'inc_pts_twin': _safe(row.iloc[18]) if len(row) > 18 else 0,
                'inc_pts_inet': _safe(row.iloc[19]) if len(row) > 19 else 0,
                'inc_pts_net': _safe(row.iloc[20]) if len(row) > 20 else 0,
                'inc_pts_other': _safe(row.iloc[21]) if len(row) > 21 else 0,
                # 新增积分
                'new_pts_total': _safe(row.iloc[22]) if len(row) > 22 else 0,
                'new_pts_base': _safe(row.iloc[23]) if len(row) > 23 else 0,
                'new_pts_twin': _safe(row.iloc[24]) if len(row) > 24 else 0,
                # 存量积分
                'stock_pts_total': _safe(row.iloc[25]) if len(row) > 25 else 0,
                'stock_pts_base': _safe(row.iloc[26]) if len(row) > 26 else 0,
                'stock_pts_twin': _safe(row.iloc[27]) if len(row) > 27 else 0,
                # 全光组网
                'gateway_count': _safe(row.iloc[41]) if len(row) > 41 else 0,
            })
        result['person_monthly'] = records

    # ── 揽装人维度（日）─────────────────────────────────────────────────────
    sheet_name_day = "揽装人维度（日)"
    if sheet_name_day in all_sheets:
        df = all_sheets[sheet_name_day]
        data_rows = df.iloc[5:].reset_index(drop=True)
        date_str = _parse_data_date(df.iloc[0, 0])
        if date_str and not result['data_date']:
            result['data_date'] = date_str

        records = []
        for _, row in data_rows.iterrows():
            name = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""
            if not name or name in ("nan", "客户经理名称"):
                continue
            records.append({
                'name': name,
                'district': str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else "",
                'team': str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else "",
                'new_gaotao': _safe(row.iloc[5]),
                'stock_gaotao': _safe(row.iloc[6]),
                'inc_pts_total': _safe(row.iloc[13]) if len(row) > 13 else 0,
                'inc_pts_base': _safe(row.iloc[14]) if len(row) > 14 else 0,
                'inc_pts_twin': _safe(row.iloc[18]) if len(row) > 18 else 0,
                'new_pts_total': _safe(row.iloc[22]) if len(row) > 22 else 0,
            })
        result['person_daily'] = records

    # ── 区县责任田积分（月）────────────────────────────────────────────────────
    # 列索引（pandas 0-based）:
    #   col3=净增积分全业务, col4=基本面, col5-12=基本面分项(移动/宽带/固话/ITV/智家/到期/降值/拆机)
    #   col13=双线, col14=互专, col15=组网, col16=双线降值, col17=双线拆机
    #   col18=其他业务, col19=云, col20=物, col21=其他拆机
    sheet_dist_month = "区县责任田积分(月）"
    if sheet_dist_month in all_sheets:
        df = all_sheets[sheet_dist_month]
        data_rows = df.iloc[3:].reset_index(drop=True)
        date_str = _parse_data_date(df.iloc[3, 0] if len(df) > 3 else None)
        if date_str and not result['data_date']:
            result['data_date'] = date_str

        # 读揽装局向维度G列（落格率），找端州行 col6=增量积分落格率
        g_rate_map = {}   # {district: 落格率}
        lxjx_sheet = "揽装局向维度（月累）"
        if lxjx_sheet in all_sheets:
            df_lx = all_sheets[lxjx_sheet]
            for idx in range(len(df_lx)):
                r = df_lx.iloc[idx]
                dist_name = str(r.iloc[2]).strip() if pd.notna(r.iloc[2]) else ""
                if dist_name and dist_name not in ("nan", "区县", "序号"):
                    rate_val = _safe(r.iloc[6]) if len(r) > 6 else 0  # col6=G列=落格率
                    g_rate_map[dist_name] = rate_val

        records = []
        for _, row in data_rows.iterrows():
            district = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
            if not district or district in ("nan", "全市"):
                continue
            net = _safe(row.iloc[3])
            base = _safe(row.iloc[4])
            twin = _safe(row.iloc[13]) if len(row) > 13 else 0
            other = _safe(row.iloc[18]) if len(row) > 18 else 0
            records.append({
                'district': district,
                'net_pts': net,
                'inc_pts': net,           # 净增积分就是各业务净贡献之和
                'base_pts': base,
                'base_mobile': _safe(row.iloc[5]) if len(row) > 5 else 0,
                'base_bb': _safe(row.iloc[6]) if len(row) > 6 else 0,
                'base_phone': _safe(row.iloc[7]) if len(row) > 7 else 0,
                'base_itv': _safe(row.iloc[8]) if len(row) > 8 else 0,
                'base_smart': _safe(row.iloc[9]) if len(row) > 9 else 0,
                'base_expire': _safe(row.iloc[10]) if len(row) > 10 else 0,
                'base_decline': _safe(row.iloc[11]) if len(row) > 11 else 0,
                'base_churn': _safe(row.iloc[12]) if len(row) > 12 else 0,
                'twin_pts': twin,
                'twin_inet': _safe(row.iloc[14]) if len(row) > 14 else 0,
                'twin_net': _safe(row.iloc[15]) if len(row) > 15 else 0,
                'twin_decline': _safe(row.iloc[16]) if len(row) > 16 else 0,
                'twin_churn': _safe(row.iloc[17]) if len(row) > 17 else 0,
                'other_pts': other,
                'other_cloud': _safe(row.iloc[19]) if len(row) > 19 else 0,
                'other_iot': _safe(row.iloc[20]) if len(row) > 20 else 0,
                'pts_completion_rate': g_rate_map.get(district, 0.0),
            })
        result['district_monthly'] = records

    # ── 区县责任田积分（日）────────────────────────────────────────────────────
    sheet_dist_day = "区县责任田积分(日）"
    if sheet_dist_day in all_sheets:
        df = all_sheets[sheet_dist_day]
        data_rows = df.iloc[3:].reset_index(drop=True)

        records = []
        for _, row in data_rows.iterrows():
            district = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
            if not district or district in ("nan", "全市"):
                continue
            records.append({
                'district': district,
                'net_pts': _safe(row.iloc[3]),
                'inc_pts': _safe(row.iloc[3]),  # 日数据近似
                'base_pts': _safe(row.iloc[4]) if len(row) > 4 else 0,
                'twin_pts': _safe(row.iloc[13]) if len(row) > 13 else 0,
                'other_pts': _safe(row.iloc[18]) if len(row) > 18 else 0,
            })
        result['district_daily'] = records

    # ── 网点月发展 ─────────────────────────────────────────────────────────────
    sheet_outlet = "网点月发展"
    if sheet_outlet in all_sheets:
        df = all_sheets[sheet_outlet]
        data_rows = df.iloc[3:].reset_index(drop=True)

        records = []
        for _, row in data_rows.iterrows():
            outlet_name = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
            if not outlet_name or outlet_name in ("nan",):
                continue
            records.append({
                'district': str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else "",
                'outlet_name': outlet_name,
                'outlet_code': str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else "",
                'all_dev_count': int(_safe(row.iloc[5])),
                'all_inc_pts': _safe(row.iloc[6]) if len(row) > 6 else 0,
                'all_net_pts': _safe(row.iloc[7]) if len(row) > 7 else 0,
                'all_churn_pts': _safe(row.iloc[8]) if len(row) > 8 else 0,
                'mobile_dev_count': int(_safe(row.iloc[11])) if len(row) > 11 else 0,
                'mobile_inc_pts': _safe(row.iloc[12]) if len(row) > 12 else 0,
                'bb_dev_count': int(_safe(row.iloc[17])) if len(row) > 17 else 0,
                'bb_inc_pts': _safe(row.iloc[18]) if len(row) > 18 else 0,
            })
        result['outlet_monthly'] = records

    # 如果仍未解析到日期，从文件名尝试提取
    if not result['data_date']:
        result['data_date'] = _parse_data_date(os.path.basename(file_path))
    if not result['data_date']:
        result['data_date'] = datetime.today().strftime('%Y-%m-%d')

    return result
