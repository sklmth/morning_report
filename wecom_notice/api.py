from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from wecom_notice.config import CUSTOMER_MANAGERS, GAOZHUANG_STAFF, MANAGER_RECIPIENTS, ZHIYUN_ENGINEERS
from wecom_notice.db import (
    add_send_log,
    get_fill_statistics,
    get_records,
    get_reminder_logs,
    get_rule,
    get_rules,
    get_send_logs,
    init_db,
    latest_upload,
    save_rule,
    upsert_records,
)
from wecom_notice.excel_export import export_cumulative_stats
from wecom_notice.parser import normalize_record
from wecom_notice.reporter import build_cumulative_statistics, build_report
from wecom_notice.sender import send_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # 注意：调度器默认不启动，需要通过API手动启用
    app.state.scheduler = None
    yield
    # 关闭调度器
    if hasattr(app.state, "scheduler") and app.state.scheduler:
        from wecom_notice.scheduler import stop_scheduler
        stop_scheduler(app.state.scheduler)


app = FastAPI(title="企业微信通报 API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_FRONTEND_DIR = Path(__file__).parent / "frontend"

@app.get("/")
def index():
    return FileResponse(str(_FRONTEND_DIR / "index.html"))


class UploadRequest(BaseModel):
    source: str = "ks_bitable"
    report_version: str = "wecom_notice_v1"
    file_name: str = ""
    sheet_id: str = ""
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ReportRequest(BaseModel):
    rule_key: str
    target_date: str = ""


class RuleUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    trigger_type: str | None = None
    cron_expr: str | None = None
    filter: dict[str, Any] | None = None
    recipient_policy: dict[str, Any] | None = None
    template_key: str | None = None


def tomorrow() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def get_report(payload: ReportRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    rule = get_rule(payload.rule_key)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    report = build_report(payload.target_date or tomorrow(), rule)
    return rule, report


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "wecom_notice"}


@app.post("/api/airscript/upload")
def airscript_upload(payload: UploadRequest):
    if payload.report_version != "wecom_notice_v1":
        raise HTTPException(status_code=400, detail="不支持的 report_version")
    if not payload.rows:
        raise HTTPException(status_code=400, detail="rows 不能为空")
    result = upsert_records([normalize_record(row) for row in payload.rows])
    return {"ok": True, "received": len(payload.rows), **result}


@app.get("/api/records")
def records(
    date_value: str = Query("", alias="date"),
    manager: str = "",
    status: str = "",
    limit: int = 300,
):
    return {"records": get_records(date_value, manager, status, limit)}


@app.get("/api/summary")
def summary(date_value: str = Query("", alias="date")):
    from wecom_notice.db import get_manager_history_counts

    target_date = date_value or tomorrow()
    records = get_records(appointment_date=target_date)
    report_rule = get_rule("missing_tomorrow_booking")
    shortage = build_report(target_date, report_rule) if report_rule else {"items": []}

    manager_progress = []
    for manager in CUSTOMER_MANAGERS:
        booked = sum(1 for record in records if record["manager_name"] == manager["name"])
        history_counts = get_manager_history_counts(manager["name"], target_date)
        manager_progress.append({
            "name": manager["name"],
            "team": manager.get("team", ""),
            "booked": booked,
            "history_counts": history_counts
        })

    return {
        "date": target_date,
        "roster_count": len(CUSTOMER_MANAGERS),
        "booked_manager_count": len({record["manager_name"] for record in records if record["manager_name"]}),
        "qualified_manager_count": len(CUSTOMER_MANAGERS) - len(shortage["items"]),
        "shortage_manager_count": len(shortage["items"]),
        "appointment_count": len(records),
        "dispatch_count": sum(1 for record in records if record["need_dispatch"] in {"是", "需要", "1", "true", "True"}),
        "latest_upload": latest_upload(),
        "manager_progress": manager_progress,
    }


@app.get("/api/config/roster")
def roster():
    return {"customer_managers": CUSTOMER_MANAGERS, "manager_recipients": MANAGER_RECIPIENTS}


@app.get("/api/config/delivery-staff")
def delivery_staff():
    """获取预约交付人员名单（高端装维+智云工程师）"""
    return {
        "gaozhuang": GAOZHUANG_STAFF,
        "zhiyun": ZHIYUN_ENGINEERS,
        "all": GAOZHUANG_STAFF + ZHIYUN_ENGINEERS
    }


@app.get("/api/config/rules")
def rules():
    return {"rules": get_rules()}


@app.put("/api/config/rules/{rule_key}")
def update_rule(rule_key: str, payload: RuleUpdate):
    try:
        return {"rule": save_rule(rule_key, payload.model_dump(exclude_none=True))}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/report/preview")
def preview_report(payload: ReportRequest):
    rule, report = get_report(payload)
    return {"rule": rule, "target_date": payload.target_date or tomorrow(), **report}


@app.post("/api/report/send")
def send_report(payload: ReportRequest):
    rule, report = get_report(payload)
    record_ids = [record["id"] for record in report["records"]]
    try:
        response = send_text(report["message"], report["recipients"])
    except RuntimeError as exc:
        add_send_log(rule["rule_key"], "failed", report["message"], report["recipients"], record_ids, error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    add_send_log(rule["rule_key"], "success", report["mess.age"], report["recipients"], record_ids, webhook_response=str(response))
    return {"ok": True, "response": response, "mentioned": report["recipients"]}


@app.post("/api/scheduler/run-once")
def run_once(payload: ReportRequest):
    return send_report(payload)


@app.get("/api/send-logs")
def send_logs(limit: int = 100):
    return {"logs": get_send_logs(limit)}


@app.get("/api/statistics/cumulative")
def cumulative_statistics(
    start_date: str = "",
    end_date: str = "",
):
    """查询累计统计（漏填、准时、超时）"""
    stats = build_cumulative_statistics(start_date, end_date)
    return stats


@app.get("/api/statistics/export")
def export_statistics(start_date: str = "", end_date: str = ""):
    """导出累计统计Excel"""
    stats = build_cumulative_statistics(start_date, end_date)

    if not end_date:
        end_date = date.today().isoformat()
    if not start_date:
        start_date = (date.today() - timedelta(days=30)).isoformat()

    date_range = f"{start_date}至{end_date}"

    # 确保输出目录存在
    runtime_dir = Path(__file__).parent.parent / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    out_path = runtime_dir / f"预约填报统计_{start_date}_{end_date}.xlsx"
    export_cumulative_stats(stats, str(out_path), date_range)

    return FileResponse(
        str(out_path),
        filename=f"预约填报统计{date_range}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.get("/api/statistics/details")
def statistics_details(
    start_date: str = "",
    end_date: str = "",
    manager_name: str = "",
    fill_status: str = ""
):
    """查询填报统计明细"""
    records = get_fill_statistics(start_date, end_date, manager_name, fill_status)
    return {"statistics": records, "count": len(records)}


@app.get("/api/reminders/logs")
def reminder_logs(date: str = "", manager_name: str = "", limit: int = 100):
    """查询提醒日志"""
    logs = get_reminder_logs(date, manager_name, limit)
    return {"logs": logs, "count": len(logs)}


@app.get("/api/scheduler/status")
def scheduler_status():
    """查询调度器状态"""
    if not hasattr(app.state, "scheduler") or app.state.scheduler is None:
        return {"running": False, "jobs": []}

    jobs = []
    for job in app.state.scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    return {"running": True, "jobs": jobs, "count": len(jobs)}


@app.post("/api/scheduler/start")
def start_scheduler_api():
    """启动调度器"""
    if hasattr(app.state, "scheduler") and app.state.scheduler:
        return {"ok": False, "message": "调度器已在运行"}

    from wecom_notice.scheduler import start_scheduler
    app.state.scheduler = start_scheduler(enabled=True)

    return {
        "ok": True,
        "message": "调度器已启动",
        "job_count": len(app.state.scheduler.get_jobs())
    }


@app.post("/api/scheduler/stop")
def stop_scheduler_api():
    """停止调度器"""
    if not hasattr(app.state, "scheduler") or app.state.scheduler is None:
        return {"ok": False, "message": "调度器未运行"}

    from wecom_notice.scheduler import stop_scheduler
    stop_scheduler(app.state.scheduler)
    app.state.scheduler = None

    return {"ok": True, "message": "调度器已停止"}


@app.post("/api/scheduler/trigger/{job_id}")
def trigger_job_manually(job_id: str):
    """手动触发指定任务"""
    if not hasattr(app.state, "scheduler") or app.state.scheduler is None:
        raise HTTPException(status_code=400, detail="调度器未运行")

    job = app.state.scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 立即执行一次
    job.func()

    return {"ok": True, "message": f"任务 {job_id} 已手动触发"}


@app.post("/api/kingsoft/trigger-sync")
def trigger_kingsoft_sync():
    """手动触发金山文档数据同步"""
    from wecom_notice.kingsoft_trigger import trigger_kingsoft_data_sync
    from wecom_notice.db import add_send_log

    try:
        result = trigger_kingsoft_data_sync()

        add_send_log(
            rule_key="kingsoft_data_sync_manual",
            status="success",
            message_text="手动触发金山文档数据同步",
            mentioned=[],
            record_ids=[],
            webhook_response=str(result)
        )

        return {
            "ok": True,
            "message": "金山文档数据同步已触发",
            "response": result
        }

    except Exception as e:
        add_send_log(
            rule_key="kingsoft_data_sync_manual",
            status="failed",
            message_text="手动触发金山文档数据同步失败",
            mentioned=[],
            record_ids=[],
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

# 前端静态文件（放在所有 API 路由之后，不会覆盖 /api/* 路由）
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
