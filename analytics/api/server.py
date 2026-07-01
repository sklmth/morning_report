"""
FastAPI 经营分析服务器 (内部端口 8992，由 nginx:8991 代理)
"""

import io
import logging
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from analytics.db import init_db, get_available_months, get_connection, db_conn
from analytics.analyzer.metrics import (
    get_overview, get_score_structure, get_person_efficiency,
    get_risk_alerts, get_branch_compare, get_trend,
)
from analytics.analyzer.forecast import get_progress_forecast
from analytics.pipeline import process_file

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Analytics DB initialized")
    yield


app = FastAPI(
    title="端州政企经营分析 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 健康检查 ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


# ─── 总览 ────────────────────────────────────────────────────────────────────────
@app.get("/api/overview")
def overview(month: Optional[str] = Query(None, description="月份 e.g. 2026-06")):
    with get_connection() as conn:
        return get_overview(month, conn)


# ─── 快照列表 ─────────────────────────────────────────────────────────────────────
@app.get("/api/snapshots")
def snapshots(limit: int = Query(50, le=200)):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, data_date, month, source_type, source_file,
                      processed_at, trigger_by, morning_report_id
               FROM data_snapshots
               ORDER BY data_date DESC, id DESC
               LIMIT ?""", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


@app.get("/api/months")
def months():
    with get_connection() as conn:
        return {"months": get_available_months(conn)}


# ─── 积分结构分析 ──────────────────────────────────────────────────────────────────
@app.get("/api/analysis/score-structure")
def score_structure(month: str = Query(..., description="月份 e.g. 2026-06")):
    with get_connection() as conn:
        return get_score_structure(month, conn)


# ─── 完成进度预测 ──────────────────────────────────────────────────────────────────
@app.get("/api/analysis/progress")
def progress(month: str = Query(..., description="月份 e.g. 2026-06")):
    with get_connection() as conn:
        return get_progress_forecast(month, conn)


# ─── 人员效能 ──────────────────────────────────────────────────────────────────────
@app.get("/api/analysis/person-efficiency")
def person_efficiency(month: str = Query(..., description="月份 e.g. 2026-06")):
    with get_connection() as conn:
        return get_person_efficiency(month, conn)


# ─── 县分横向对比 ──────────────────────────────────────────────────────────────────
@app.get("/api/analysis/branch-compare")
def branch_compare(month: str = Query(..., description="月份 e.g. 2026-06")):
    with get_connection() as conn:
        return get_branch_compare(month, conn)


# ─── 存量风险预警 ──────────────────────────────────────────────────────────────────
@app.get("/api/analysis/risk-alerts")
def risk_alerts(month: str = Query(..., description="月份 e.g. 2026-06")):
    with get_connection() as conn:
        return get_risk_alerts(month, conn)


# ─── 月度趋势 ──────────────────────────────────────────────────────────────────────
@app.get("/api/analysis/trend")
def trend(months_count: int = Query(6, alias="months", ge=1, le=24)):
    with get_connection() as conn:
        return get_trend(months_count, conn)


# ─── 上传历史 Excel ────────────────────────────────────────────────────────────────
@app.post("/api/upload")
async def upload_excel(files: list[UploadFile] = File(...)):
    """
    上传一个或多个 Excel 文件（完美一单 / 营服报表）
    自动识别类型并解析入库
    """
    results = []
    upload_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "runtime", "analytics_uploads"
    )
    os.makedirs(upload_dir, exist_ok=True)

    logger.info("Upload request: %d file(s): %s",
                len(files), ", ".join(f.filename for f in files))

    for f in files:
        if not f.filename.endswith(('.xlsx', '.xls')):
            logger.warning("Upload rejected (bad ext): %s", f.filename)
            results.append({"file": f.filename, "status": "error", "msg": "仅支持 xlsx/xls 格式"})
            continue

        # 保存上传文件
        dest = os.path.join(upload_dir, f.filename)
        try:
            with open(dest, "wb") as out:
                shutil.copyfileobj(f.file, out)
            size = os.path.getsize(dest)
            logger.info("Upload saved: %s (%d bytes) -> %s", f.filename, size, dest)
        except OSError as e:
            logger.exception("Upload save failed: %s", f.filename)
            results.append({"file": f.filename, "status": "error", "msg": f"保存失败: {e}"})
            continue

        # 处理入库
        r = process_file(dest, trigger_by="upload")
        r["file"] = f.filename
        if r.get("status") == "ok":
            logger.info("Upload processed OK: %s -> %s", f.filename, r.get("msg", ""))
        else:
            logger.error("Upload process failed: %s -> %s", f.filename, r.get("msg", ""))
        results.append(r)

    ok_n = sum(1 for r in results if r.get("status") == "ok")
    logger.info("Upload done: %d ok / %d total", ok_n, len(results))
    return {"results": results}


# ─── 导出分析 Excel ────────────────────────────────────────────────────────────────
@app.get("/api/export/excel")
def export_excel(month: str = Query(...)):
    """导出指定月份的完整分析报告为 Excel"""
    from analytics.excel_export import build_analysis_excel
    buf = io.BytesIO()
    try:
        build_analysis_excel(month, buf)
    except Exception as e:
        logger.exception("Export excel failed: month=%s", month)
        raise HTTPException(status_code=500, detail=str(e))
    buf.seek(0)
    logger.info("Export excel OK: month=%s (%d bytes)", month, buf.getbuffer().nbytes)
    filename = f"经营分析_{month}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )


# ─── 人员效能原始数据（调试用）────────────────────────────────────────────────────
@app.get("/api/raw/person-monthly")
def raw_person_monthly(month: str = Query(...), name: Optional[str] = Query(None)):
    with get_connection() as conn:
        if name:
            rows = conn.execute(
                "SELECT * FROM person_monthly_metrics WHERE month=? AND name=? ORDER BY data_date DESC",
                (month, name)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM person_monthly_metrics WHERE month=? ORDER BY name, data_date DESC",
                (month,)
            ).fetchall()
        return [dict(r) for r in rows]
