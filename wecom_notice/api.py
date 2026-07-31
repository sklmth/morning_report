from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from wecom_notice.config import CUSTOMER_MANAGERS, MANAGER_RECIPIENTS
from wecom_notice.db import add_send_log, get_records, get_rule, get_rules, get_send_logs, init_db, latest_upload, save_rule, upsert_records
from wecom_notice.parser import normalize_record
from wecom_notice.reporter import build_report
from wecom_notice.sender import send_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="企业微信通报 API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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
    target_date = date_value or tomorrow()
    records = get_records(appointment_date=target_date)
    report_rule = get_rule("missing_tomorrow_booking")
    shortage = build_report(target_date, report_rule) if report_rule else {"items": []}
    return {
        "date": target_date,
        "roster_count": len(CUSTOMER_MANAGERS),
        "booked_manager_count": len({record["manager_name"] for record in records if record["manager_name"]}),
        "qualified_manager_count": len(CUSTOMER_MANAGERS) - len(shortage["items"]),
        "shortage_manager_count": len(shortage["items"]),
        "appointment_count": len(records),
        "dispatch_count": sum(1 for record in records if record["need_dispatch"] in {"是", "需要", "1", "true", "True"}),
        "latest_upload": latest_upload(),
        "manager_progress": [
            {"name": manager["name"], "booked": sum(1 for record in records if record["manager_name"] == manager["name"])}
            for manager in CUSTOMER_MANAGERS
        ],
    }


@app.get("/api/config/roster")
def roster():
    return {"customer_managers": CUSTOMER_MANAGERS, "manager_recipients": MANAGER_RECIPIENTS}


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
    add_send_log(rule["rule_key"], "success", report["message"], report["recipients"], record_ids, webhook_response=str(response))
    return {"ok": True, "response": response, "mentioned": report["recipients"]}


@app.post("/api/scheduler/run-once")
def run_once(payload: ReportRequest):
    return send_report(payload)


@app.get("/api/send-logs")
def send_logs(limit: int = 100):
    return {"logs": get_send_logs(limit)}
