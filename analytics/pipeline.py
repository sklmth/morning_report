"""
经营分析数据入库调度器
统一调用 extractor 和 db，将 wanmei/yingfu 数据写入 analytics.db
"""

import os
import logging
from typing import Optional

from analytics.db import (
    get_connection, init_db, upsert_snapshot, bulk_insert
)
from analytics.extractor.wanmei import extract_wanmei
from analytics.extractor.yingfu import extract_yingfu

logger = logging.getLogger(__name__)


def _classify_file(file_path: str) -> Optional[str]:
    """根据文件名判断是完美一单还是营服报表"""
    name = os.path.basename(file_path).lower()
    if "完美一单" in name or "wanmei" in name:
        return "wanmei"
    if "营服" in name or "业务通报" in name or "yingfu" in name:
        return "yingfu"
    # 尝试读取 sheet 名探测
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True)
        sheets = wb.sheetnames
        wb.close()
        if any("揽装人维度" in s for s in sheets):
            return "wanmei"
        if any("071人员统计" in s or "中心人员效能" in s for s in sheets):
            return "yingfu"
    except Exception:
        pass
    return None


def process_file(file_path: str, trigger_by: str = "manual",
                 morning_report_id: Optional[int] = None,
                 db_path: Optional[str] = None) -> dict:
    """
    处理单个 Excel 文件，提取数据写入 analytics.db
    返回 {'status': 'ok'/'error', 'msg': ..., 'snapshot_id': int}
    """
    init_db(db_path)
    conn = get_connection(db_path)

    try:
        ftype = _classify_file(file_path)
        if ftype is None:
            return {"status": "error", "msg": f"无法识别文件类型: {os.path.basename(file_path)}"}

        if ftype == "wanmei":
            data = extract_wanmei(file_path)
            data_date = data['data_date']
            snap_id = upsert_snapshot(
                conn, data_date, "wanmei",
                os.path.basename(file_path), trigger_by, morning_report_id
            )
            # 注入 snapshot_id / data_date / month
            month = data_date[:7]

            def _enrich(rows):
                for r in rows:
                    r['snapshot_id'] = snap_id
                    r['data_date'] = data_date
                    r['month'] = month
                return rows

            n_pm = bulk_insert(conn, "person_monthly_metrics", _enrich(data.get('person_monthly', [])))
            n_pd = bulk_insert(conn, "person_daily_metrics", _enrich(data.get('person_daily', [])))
            n_dm = bulk_insert(conn, "district_monthly_metrics", _enrich(data.get('district_monthly', [])))
            n_dd = bulk_insert(conn, "district_daily_metrics", _enrich(data.get('district_daily', [])))
            n_om = bulk_insert(conn, "outlet_monthly_metrics", _enrich(data.get('outlet_monthly', [])))
            logger.info(
                "wanmei %s: persons=%d/%d districts=%d/%d outlets=%d",
                data_date, n_pm, n_pd, n_dm, n_dd, n_om
            )
            return {"status": "ok", "snapshot_id": snap_id,
                    "data_date": data_date, "source_type": "wanmei",
                    "msg": f"完美一单入库: {n_pm}条人员月累, {n_dm}条区县月累, {n_om}条网点"}

        else:  # yingfu
            data = extract_yingfu(file_path)
            data_date = data['data_date']
            snap_id = upsert_snapshot(
                conn, data_date, "yingfu",
                os.path.basename(file_path), trigger_by, morning_report_id
            )
            month = data_date[:7]

            def _enrich(rows):
                for r in rows:
                    r['snapshot_id'] = snap_id
                    r['data_date'] = data_date
                    r['month'] = month
                return rows

            n_se = bulk_insert(conn, "staff_efficiency", _enrich(data.get('staff_efficiency', [])))
            n_st = bulk_insert(conn, "staff_incentive_tier", _enrich(data.get('staff_incentive_tier', [])))
            n_cp = bulk_insert(conn, "cp_pair_metrics", _enrich(data.get('cp_pair_metrics', [])))
            n_ac = bulk_insert(conn, "area_contract_metrics", _enrich(data.get('area_contract_metrics', [])))
            logger.info(
                "yingfu %s: staff_eff=%d tiers=%d cp=%d areas=%d",
                data_date, n_se, n_st, n_cp, n_ac
            )
            return {"status": "ok", "snapshot_id": snap_id,
                    "data_date": data_date, "source_type": "yingfu",
                    "msg": f"营服报表入库: {n_se}条人员效能, {n_st}条激励档位, {n_cp}条CP对"}

    except Exception as e:
        logger.exception("process_file failed: %s", file_path)
        return {"status": "error", "msg": str(e)}
    finally:
        conn.close()


def process_files_list(file_paths: list, **kwargs) -> list[dict]:
    """批量处理文件列表"""
    return [process_file(fp, **kwargs) for fp in file_paths if os.path.isfile(fp)]
