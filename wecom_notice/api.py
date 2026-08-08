import logging
import base64
import calendar
import os
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from wecom_notice.config import (
    CUSTOMER_MANAGERS,
    GAOZHUANG_STAFF,
    MANAGER_RECIPIENTS,
    TEST_RECIPIENTS,
    ZHIYUN_ENGINEERS,
    find_recipients,
)
from wecom_notice.db import (
    add_send_log,
    count_send_logs,
    get_fill_statistics,
    get_records,
    get_reminder_logs,
    get_rule,
    get_rules,
    get_send_logs,
    get_setting,
    init_db,
    latest_upload,
    mark_airscript_upload_received,
    save_rule,
    save_setting,
    upsert_records,
)
from wecom_notice.excel_export import export_cumulative_stats
from wecom_notice.parser import normalize_record
from wecom_notice.reporter import build_cumulative_statistics, build_report, default_target_date
from wecom_notice.sender import send_text, send_markdown, send_image, send_news, send_template_card


logger = logging.getLogger(__name__)

# 调度器开关的持久化键。存在 app_settings 表里，这样服务重启（部署、崩溃、
# 机器重启）后能自动恢复到停机前的状态，不需要有人再去点一次「启动」。
SCHEDULER_ENABLED_KEY = "scheduler_enabled"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.scheduler = None

    # 重启自愈：上次是运行状态就自动拉起，否则保持停止
    if get_setting(SCHEDULER_ENABLED_KEY, "false") == "true":
        try:
            from wecom_notice.scheduler import start_scheduler
            app.state.scheduler = start_scheduler(enabled=True)
            logger.info("检测到调度器开关为开启状态，已随服务自动恢复")
        except Exception as exc:
            logger.error(f"调度器自动恢复失败：{exc}")

    yield

    # 关闭调度器。注意不清除开关，重启后仍按开启状态恢复。
    if getattr(app.state, "scheduler", None):
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
    # 手动发送时的覆盖项：正文可在前端编辑，收件人可自由勾选。
    # 为 None 表示沿用模板生成的默认值。
    message: str | None = None
    recipient_names: list[str] | None = None
    # 规则专属参数（如 performance_award_notice 的 month / award_round）
    params: dict[str, Any] | None = None


class RuleUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    trigger_type: str | None = None
    cron_expr: str | None = None
    filter: dict[str, Any] | None = None
    recipient_policy: dict[str, Any] | None = None
    template_key: str | None = None


def tomorrow() -> str:
    """下一个工作日：周一~周四为次日，周五为下周一。"""
    return default_target_date()


def get_report(payload: ReportRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    rule = get_rule(payload.rule_key)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    # 前端传入的 params（如 month、award_round）覆盖规则默认 params
    if payload.params:
        rule = {**rule, "params": {**(rule.get("params") or {}), **payload.params}}
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
    upload_received_at = mark_airscript_upload_received()
    return {"ok": True, "received": len(payload.rows), "upload_received_at": upload_received_at, **result}


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


@app.get("/api/config/recipients")
def recipient_options():
    """手动发送通报时可勾选的接收人分组（客户经理 / 管理者 / 测试）。"""

    def brief(person: dict[str, Any], group: str, group_label: str) -> dict[str, Any]:
        return {
            "name": person["name"],
            "group": group,
            "group_label": group_label,
            "label": person.get("title") or person.get("team", ""),
            "mentionable": bool(person.get("wecom_userid") or person.get("mobile")),
        }

    return {
        "groups": [
            {
                "key": "customer_managers",
                "label": "客户经理",
                "members": [brief(p, "customer_managers", "客户经理") for p in CUSTOMER_MANAGERS],
            },
            {
                "key": "management",
                "label": "管理者",
                "members": [brief(p, "management", "管理者") for p in MANAGER_RECIPIENTS],
            },
            {
                "key": "testers",
                "label": "测试",
                "members": [brief(p, "testers", "测试") for p in TEST_RECIPIENTS],
            },
        ]
    }


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

    # 前端编辑过的正文优先；勾选过收件人时以勾选结果为准（可为空，表示不 @ 任何人）
    message = payload.message if payload.message is not None else report["message"]
    recipients = (
        find_recipients(payload.recipient_names)
        if payload.recipient_names is not None
        else report["recipients"]
    )
    if not message.strip():
        raise HTTPException(status_code=400, detail="消息内容为空，无法发送")

    try:
        response = send_text(message, recipients)
    except RuntimeError as exc:
        add_send_log(rule["rule_key"], "failed", message, recipients, record_ids, error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    add_send_log(rule["rule_key"], "success", message, recipients, record_ids, webhook_response=str(response))
    return {"ok": True, "response": response, "mentioned": recipients}


@app.post("/api/scheduler/run-once")
def run_once(payload: ReportRequest):
    return send_report(payload)


@app.get("/api/send-logs")
def send_logs(limit: int = 20, offset: int = 0):
    """分页取运行日志。counts 为全量统计，不随分页变化。"""
    counts = count_send_logs()
    logs = get_send_logs(limit, offset)
    page_size = min(max(limit, 1), 500)
    return {
        "logs": logs,
        "total": counts["total"],
        "success_count": counts["success_count"],
        "failed_count": counts["failed_count"],
        "limit": page_size,
        "offset": max(offset, 0),
        "page_count": max(1, -(-counts["total"] // page_size)),
    }


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
    """查询调度器状态。desired 为持久化的开关意图，running 为进程内实际状态。"""
    desired = get_setting(SCHEDULER_ENABLED_KEY, "false") == "true"
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is None:
        return {"running": False, "desired": desired, "jobs": [], "count": 0}

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        })
    jobs.sort(key=lambda job: (job["next_run_time"] is None, job["next_run_time"] or ""))

    return {"running": True, "desired": desired, "jobs": jobs, "count": len(jobs)}


@app.post("/api/scheduler/start")
def start_scheduler_api():
    """启动调度器，并把开关落库，使服务重启后自动恢复。"""
    if getattr(app.state, "scheduler", None):
        save_setting(SCHEDULER_ENABLED_KEY, "true")
        return {"ok": False, "message": "调度器已在运行"}

    from wecom_notice.scheduler import start_scheduler
    app.state.scheduler = start_scheduler(enabled=True)
    save_setting(SCHEDULER_ENABLED_KEY, "true")

    return {
        "ok": True,
        "message": "调度器已启动",
        "job_count": len(app.state.scheduler.get_jobs())
    }


@app.post("/api/scheduler/stop")
def stop_scheduler_api():
    """停止调度器，并把开关落库，使服务重启后保持停止。"""
    save_setting(SCHEDULER_ENABLED_KEY, "false")
    if getattr(app.state, "scheduler", None) is None:
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

@app.get("/api/config/settings")
def get_settings():
    """读取应用设置"""
    return {
        "fine_enabled": get_setting("fine_enabled", "false") == "true",
        "fine_rules_enabled": get_setting("fine_rules_enabled", "false") == "true",
    }


class SettingsBody(BaseModel):
    # 两个开关相互独立，均可单独提交（不传则保持原值）
    fine_enabled: bool | None = Field(None, description="是否在提醒中显示本月应上交金额（事后账单）")
    fine_rules_enabled: bool | None = Field(None, description="是否在提醒中附上基金规则警示（事前警醒）")


@app.post("/api/config/settings")
def post_settings(body: SettingsBody):
    """保存应用设置。只写传了的字段，未传的保持原值。"""
    if body.fine_enabled is not None:
        save_setting("fine_enabled", "true" if body.fine_enabled else "false")
    if body.fine_rules_enabled is not None:
        save_setting("fine_rules_enabled", "true" if body.fine_rules_enabled else "false")
    return {"ok": True, **get_settings()}


class SendRulesRequest(BaseModel):
    recipient_names: list[str] = Field(default_factory=list, description="接收人姓名列表")


class SendCustomMessageRequest(BaseModel):
    message_type: str = Field(..., description="消息类型: text, markdown, image, news, template_card")
    content: dict = Field(..., description="消息内容")
    recipient_names: list[str] = Field(default_factory=list, description="接收人姓名列表（用于@提醒）")
    mention_text: str = Field(default="", description="当消息类型不支持@时，额外发送的文本消息")


@app.post("/api/report/send-custom")
def send_custom_message(payload: SendCustomMessageRequest):
    """发送自定义消息到企业微信"""

    # 查找接收人
    recipients = find_recipients(payload.recipient_names) if payload.recipient_names else []

    try:
        # 根据消息类型发送
        if payload.message_type == "text":
            # text 类型直接支持 @
            text_content = payload.content.get("text", "")
            if not text_content.strip():
                raise HTTPException(status_code=400, detail="文本内容为空")
            response = send_text(text_content, recipients)
            add_send_log("custom_text", "success", text_content, recipients, [], webhook_response=str(response))

        elif payload.message_type == "markdown":
            # markdown 不支持 @，需要先发 markdown，再发 text @人
            markdown_content = payload.content.get("content", "")
            if not markdown_content.strip():
                raise HTTPException(status_code=400, detail="Markdown 内容为空")

            # 发送 markdown 消息
            response = send_markdown(markdown_content)
            add_send_log("custom_markdown", "success", markdown_content, [], [], webhook_response=str(response))

            # 如果有接收人，额外发送 text @人
            if recipients and payload.mention_text.strip():
                mention_response = send_text(payload.mention_text, recipients)
                add_send_log("custom_markdown_mention", "success", payload.mention_text, recipients, [], webhook_response=str(mention_response))

        elif payload.message_type == "image":
            # image 不支持 @
            base64_content = payload.content.get("base64", "")
            md5_value = payload.content.get("md5", "")
            if not base64_content or not md5_value:
                raise HTTPException(status_code=400, detail="图片内容或 MD5 为空")

            # 发送图片消息
            response = send_image(base64_content, md5_value)
            add_send_log("custom_image", "success", f"[图片消息 md5={md5_value}]", [], [], webhook_response=str(response))

            # 如果有接收人，额外发送 text @人
            if recipients and payload.mention_text.strip():
                mention_response = send_text(payload.mention_text, recipients)
                add_send_log("custom_image_mention", "success", payload.mention_text, recipients, [], webhook_response=str(mention_response))

        elif payload.message_type == "news":
            # news 不支持 @
            articles = payload.content.get("articles", [])
            if not articles:
                raise HTTPException(status_code=400, detail="图文列表为空")

            # 发送图文消息
            response = send_news(articles)
            add_send_log("custom_news", "success", f"[图文消息 {len(articles)} 条]", [], [], webhook_response=str(response))

            # 如果有接收人，额外发送 text @人
            if recipients and payload.mention_text.strip():
                mention_response = send_text(payload.mention_text, recipients)
                add_send_log("custom_news_mention", "success", payload.mention_text, recipients, [], webhook_response=str(mention_response))

        elif payload.message_type == "template_card":
            # template_card 不支持 @
            card_type = payload.content.get("card_type", "")
            if card_type not in ["text_notice", "news_notice"]:
                raise HTTPException(status_code=400, detail=f"不支持的卡片类型: {card_type}")

            # 发送模板卡片消息
            response = send_template_card(card_type, payload.content)
            add_send_log(f"custom_template_card_{card_type}", "success", f"[模板卡片消息 {card_type}]", [], [], webhook_response=str(response))

            # 如果有接收人，额外发送 text @人
            if recipients and payload.mention_text.strip():
                mention_response = send_text(payload.mention_text, recipients)
                add_send_log("custom_template_card_mention", "success", payload.mention_text, recipients, [], webhook_response=str(mention_response))

        else:
            raise HTTPException(status_code=400, detail=f"不支持的消息类型: {payload.message_type}")

    except RuntimeError as exc:
        add_send_log(f"custom_{payload.message_type}", "failed", str(payload.content), recipients, [], error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"ok": True, "message_type": payload.message_type, "mentioned": recipients}


class UploadPicRequest(BaseModel):
    data_url: str = Field(..., description="图片 data URL (data:image/xxx;base64,...)")


_UPLOADS_DIR = _FRONTEND_DIR / "uploads"
_ALLOWED_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_PUBLIC_UPLOAD_BASE_URL = os.environ.get(
    "WECOM_NOTICE_PUBLIC_UPLOAD_BASE_URL",
    "https://shanguantang.site/wecom-notice/uploads",
).rstrip("/")


@app.post("/api/upload-pic")
def upload_pic(payload: UploadPicRequest):
    """接收前端 data URL，保存为文件，返回可公开访问的 URL"""
    data_url = payload.data_url
    # 解析 data URL: data:<mime>;base64,<data>
    if not data_url.startswith("data:"):
        raise HTTPException(status_code=400, detail="不是合法的 data URL")
    try:
        header, b64_data = data_url.split(",", 1)
        mime = header.split(":")[1].split(";")[0]
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="data URL 格式错误")

    if mime not in _ALLOWED_MIME:
        raise HTTPException(status_code=400, detail=f"不支持的图片类型: {mime}")

    ext = mime.split("/")[1]
    if ext == "jpeg":
        ext = "jpg"

    try:
        img_bytes = base64.b64decode(b64_data)
    except Exception:
        raise HTTPException(status_code=400, detail="base64 解码失败")

    if len(img_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小超过 10MB")

    _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    (  _UPLOADS_DIR / filename).write_bytes(img_bytes)

    return {
        "ok": True,
        "url": f"{_PUBLIC_UPLOAD_BASE_URL}/{filename}",
    }


@app.post("/api/report/send-rules")
def send_rules_introduction(payload: SendRulesRequest):
    """发送规则介绍消息到企业微信"""

    # 规则介绍消息内容
    message = """📋【预约填报与奖励抵扣规则】

━━━━━━ ⏰ 填报时间规则 ━━━━━━

✅ 准时填报：19:30 前完成
⏱️ 超时填报：19:30 - 23:30 之间完成
❌ 漏填：23:30 前未完成

━━━━━━ ☕ 下午茶基金 ━━━━━━

💰 扣款标准：
   · 漏填：10 元/次
   · 超时：每累计 5 次扣 10 元
   · 按自然月统计，次月清零

💸 应缴账单：
   · 系统会统计本月扣罚合计、已抵扣金额、仍需上交金额
   · 奖品抵扣只抵扣金额，不改变准时/超时/漏填次数记录
   · 已全额抵扣时，本月暂无需上交

━━━━━━ 🎁 奖品抵扣规则 ━━━━━━

🏆 专项业绩下发奖品：
   · 由系统直接进入客户经理奖品池
   · 系统会自动用于抵扣当月扣罚
   · 抵扣后如有差额，会自动找零生成小额奖品
   · 例：筑基丹15元抵扣10元，找零生成聚灵丹5元

🎴 抽奖获得奖品：
   · 由客户经理在页面中自行选择使用
   · 未主动使用前，不会被系统自动抵扣

🔁 找零生成奖品：
   · 找零奖品会继续留在奖品池
   · 后续可继续用于抵扣扣罚

━━━━━━ 🏆 专项业绩奖励 ━━━━━━

📊 数据来源：完美一单专项业绩上传数据
🎯 奖励类型：
   · 累计综合：按右端点数据日期的本月累计业绩排名
   · 本期新增综合：按页面选择的左端点/右端点新增业绩排名

🧮 综合得分规则：
   · 综合得分最高 100 分
   · 完成率得分最高 70 分
   · 排名得分最高 30 分
   · 单项完成率最高按 100% 计
   · 本期新增任务按“新增天数 / 当月天数”折算

━━━━━━ 🎰 天命赦令 ━━━━━━

📅 休假制度：
   · 可在系统登记休假日期
   · 休假当天及前一天无需填报
   · 休假期间不计入统计

🎴 抽签系统：
   · 每 3 次准时填报 = 1 次抽签机会
   · 可选择消耗 3-7 次准时记录抽签
   · 消耗越多，中奖概率越高
   · 准时次数仅当月有效，次月清零

🎁 奖品体系：
   · 凡尘符咒：0 元（空奖）
   · 聚灵丹：5 元
   · 护身符：10 元
   · 筑基丹：15 元
   · 天罡令：20 元
   · 金丹圣果：25 元
   · 天命赦令：30 元

💡 访问地址：https://shanguantang.site/tianming

━━━━━━━━━━━━━━━━━━━━━━

准时填报，好运相伴🍀"""

    # 查找接收人
    recipients = find_recipients(payload.recipient_names) if payload.recipient_names else []

    if not message.strip():
        raise HTTPException(status_code=400, detail="消息内容为空，无法发送")

    try:
        response = send_text(message, recipients)
    except RuntimeError as exc:
        add_send_log("rules_introduction", "failed", message, recipients, [], error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    add_send_log("rules_introduction", "success", message, recipients, [], webhook_response=str(response))
    return {"ok": True, "response": response, "mentioned": recipients}


# ═══════════════════════════════════════════════════════════════════════════════
# 专项业绩奖励接口
# ═══════════════════════════════════════════════════════════════════════════════

class AwardConfigPayload(BaseModel):
    month: str
    award_round: int = 1
    rank_from: int
    rank_to: int
    metric: str = "cumulative_score"    # cumulative_score | incremental_score
    points_weight: float = 0.4
    gaotao_weight: float = 0.6
    prize_name: str
    prize_amount: int
    note: str = ""


class DispatchPayload(BaseModel):
    month: str
    award_round: int = 1
    dispatch_date: str        # YYYY-MM-DD
    left_date: str = ""       # 空表示本月开始
    right_date: str = ""      # 空表示最新上传日期


class ManualPerformancePrizePayload(BaseModel):
    month: str
    manager_name: str
    prize_name: str
    prize_amount: int
    note: str = ""


@app.post("/api/performance/upload")
async def performance_upload(file: UploadFile = File(...), month: str = Query("")):
    """上传完美一单 Excel，解析后入库。"""
    import tempfile, os
    from wecom_notice.performance import parse_wanmei_excel
    from wecom_notice.db import save_performance_upload, save_performance_stats

    if not month:
        month = date.today().strftime("%Y-%m")

    # 临时落盘
    suffix = Path(file.filename or "upload.xlsx").suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(await file.read())
        tmp.flush()
        tmp.close()
        parsed = parse_wanmei_excel(tmp.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        os.unlink(tmp.name)

    file_date = parsed.get("file_date") or date.today().isoformat()
    upload_id = save_performance_upload(month, file_date, note=file.filename or "")
    save_performance_stats(upload_id, month, parsed["stats"])

    manager_count = len(parsed["stats"])
    add_send_log(
        rule_key="performance_upload",
        status="success",
        message_text=f"[专项业绩] 上传完美一单 {month} | 文件：{file.filename} | 数据日期：{file_date} | 共 {manager_count} 人",
        mentioned=[],
        record_ids=[],
        webhook_response=f"upload_id={upload_id}",
    )
    return {"ok": True, "upload_id": upload_id, "file_date": file_date,
            "manager_count": manager_count}


@app.get("/api/performance/stats/{month}")
def performance_stats(month: str, left_date: str = Query(""), right_date: str = Query("")):
    """返回本月各轮次的累计 + 增量数据，以及本月已下发的奖励明细。"""
    from wecom_notice.performance import compute_incremental_stats
    from wecom_notice.db import (
        auto_apply_prizes,
        get_all_prize_items_month,
        get_award_configs,
        get_available_prize_total,
        get_dispatches,
        get_fill_summary_month,
        get_latest_fill_statistics_date,
        get_performance_snapshots,
        get_performance_stats,
        get_prize_change_map,
        get_prize_coverage_map,
        get_total_prize_covered,
    )
    result = compute_incremental_stats(month)
    uploads = result["uploads"]
    chronological_uploads = sorted(uploads, key=lambda u: (u.get("file_date") or "", u.get("uploaded_at") or "", u.get("id") or 0))
    def _upload_by_date(d: str) -> dict[str, Any] | None:
        matches = [u for u in chronological_uploads if (u.get("file_date") or "") == d]
        return matches[-1] if matches else None
    right_upload = _upload_by_date(right_date) if right_date else (chronological_uploads[-1] if chronological_uploads else None)
    if right_date and not right_upload:
        raise HTTPException(status_code=400, detail=f"右端点日期 {right_date} 没有对应上传数据")
    left_upload = _upload_by_date(left_date) if left_date else None
    if left_date and not left_upload:
        raise HTTPException(status_code=400, detail=f"左端点日期 {left_date} 没有对应上传数据")
    if left_date and right_upload and left_date > (right_upload.get("file_date") or ""):
        raise HTTPException(status_code=400, detail="左端点不能晚于右端点")
    selected_cumulative = []
    selected_incremental = []
    if right_upload:
        right_rows = get_performance_stats(month, upload_id=right_upload["id"])
        left_map = {}
        if left_upload:
            left_map = {r["manager_name"]: r for r in get_performance_stats(month, upload_id=left_upload["id"])}
        selected_cumulative = [
            {"manager_name": r["manager_name"], "cumulative_points": r["cumulative_points"], "cumulative_gaotao": r["cumulative_gaotao"]}
            for r in right_rows
        ]
        selected_incremental = [
            {
                "manager_name": r["manager_name"],
                "inc_points": r["cumulative_points"] - left_map.get(r["manager_name"], {}).get("cumulative_points", 0.0),
                "inc_gaotao": r["cumulative_gaotao"] - left_map.get(r["manager_name"], {}).get("cumulative_gaotao", 0.0),
            }
            for r in right_rows
        ]
    dispatches = get_dispatches(month, include_revoked=True)
    configs = get_award_configs(month)
    snapshots = get_performance_snapshots(month)
    dispatch_by_id = {d["id"]: d for d in dispatches}
    latest_upload_id = right_upload["id"] if right_upload else None
    through_date = get_latest_fill_statistics_date(month)
    fine_rows = get_fill_summary_month(month, through_date=through_date)

    # 查询统计时同步一次自动抵扣，确保后补/回填的扣罚也能被已下发奖品抵扣。
    for row in fine_rows:
        missing_count = int(row.get("missing_count") or 0)
        overtime_count = int(row.get("overtime_count") or 0)
        total_fine = missing_count * 10 + (overtime_count // 5) * 10
        if total_fine > 0:
            auto_apply_prizes(row["manager_name"], month, total_fine)

    # 自动抵扣可能产生找零奖品，因此在同步抵扣后重新读取奖品明细和映射。
    prize_items = get_all_prize_items_month(month)
    covered_map = get_prize_coverage_map(month)
    change_map = get_prize_change_map(month)
    prize_details = []
    for item in prize_items:
        d = dispatch_by_id.get(item.get("source_ref_id")) if item.get("source") == "performance" else None
        covered = covered_map.get(item["id"], 0)
        prize_details.append({
            **item,
            "covered_amount": covered,
            "change_prizes": change_map.get(item["id"], []),
            "source_label": "专项业绩奖励" if item.get("source") == "performance" else item.get("source", ""),
            "award_round": d.get("award_round") if d else None,
            "metric": d.get("metric") if d else "",
            "rank_position": d.get("rank_position") if d else None,
        })

    fine_summary = []
    def _prize_source_info(p: dict[str, Any]) -> tuple[str, str, str]:
        is_change = str(p.get("note") or "").startswith("找零")
        is_manual = str(p.get("note") or "").startswith("手动发放")
        if is_change:
            return "change", p.get("note") or "找零生成", "找零生成，可继续抵扣"
        if is_manual:
            return "performance_manual", p.get("note") or "手动发放专项业绩奖励", "系统直接抵扣"
        if p.get("source") == "performance":
            return "performance", f"专项业绩下发｜第{p.get('award_round') or '—'}轮｜{p.get('metric') or ''}", "系统直接抵扣"
        if p.get("source") == "lottery":
            return "lottery", "抽奖获得", "可在页面自行选择使用"
        return p.get("source") or "other", p.get("source_label") or p.get("source") or "其他来源", "可用"

    for row in fine_rows:
        missing_count = int(row.get("missing_count") or 0)
        overtime_count = int(row.get("overtime_count") or 0)
        missing_fine = missing_count * 10
        overtime_fine = (overtime_count // 5) * 10
        total_fine = missing_fine + overtime_fine
        covered = get_total_prize_covered(row["manager_name"], month)
        available = get_available_prize_total(row["manager_name"], month)
        available_prizes = []
        covered_prizes = []
        for p in prize_details:
            if p.get("manager_name") != row["manager_name"]:
                continue
            source_type, source_text, usage_text = _prize_source_info(p)
            prize_summary = {
                "id": p.get("id"),
                "prize_name": p.get("prize_name"),
                "face_amount": p.get("face_amount"),
                "covered_amount": p.get("covered_amount") or 0,
                "source": p.get("source"),
                "source_type": source_type,
                "source_text": source_text,
                "usage_text": usage_text,
                "award_round": p.get("award_round"),
                "metric": p.get("metric"),
                "rank_position": p.get("rank_position"),
                "note": p.get("note") or "",
                "acquired_at": p.get("acquired_at") or "",
            }
            if p.get("status") == "available":
                available_prizes.append(prize_summary)
            elif p.get("status") == "exhausted" and (p.get("covered_amount") or 0) > 0:
                covered_prizes.append(prize_summary)
        fine_summary.append({
            **row,
            "missing_fine": missing_fine,
            "overtime_fine": overtime_fine,
            "total_fine": total_fine,
            "covered_amount": covered,
            "available_prize_amount": available,
            "available_prizes": available_prizes,
            "covered_prizes": covered_prizes,
            "payable_amount": max(0, total_fine - covered),
        })
    fine_summary.sort(key=lambda r: (-(r["payable_amount"]), -(r["total_fine"]), -(r["missing_count"]), -(r["overtime_count"]), r["manager_name"]))
    return {
        "month": month,
        "uploads": result["uploads"],
        "cumulative": result["cumulative"],
        "incremental": result["incremental"],
        "selected_right_upload_id": latest_upload_id,
        "selected_left_date": left_date,
        "selected_right_date": right_upload.get("file_date") if right_upload else "",
        "selected_cumulative": selected_cumulative,
        "selected_incremental": selected_incremental,
        "selected_period": {
            "from_date": left_date,
            "to_date": right_upload.get("file_date") if right_upload else "",
            "from_label": left_date or "本月开始",
        },
        "latest_incremental": selected_incremental,
        "latest_incremental_period": {"from_date": left_date, "to_date": right_upload.get("file_date") if right_upload else ""},
        "current_incremental": selected_incremental,
        "dispatches": dispatches,
        "award_configs": configs,
        "snapshots": snapshots,
        "prize_details": prize_details,
        "fine_summary": fine_summary,
        "fine_summary_through_date": through_date,
    }


@app.get("/api/performance/stats/{month}/export")
def performance_stats_export(month: str, upload_id: int = Query(0)):
    """下载专项业绩 Excel。新增列基准：本月最新一次下发奖励快照；首次发奖前显示 "-"。"""
    from urllib.parse import quote

    from wecom_notice.performance import export_performance_excel
    from wecom_notice.db import get_latest_performance_upload, get_latest_dispatch_snapshot_map

    if not upload_id:
        latest = get_latest_performance_upload(month)
        if not latest:
            raise HTTPException(status_code=404, detail="本月暂无上传记录")
        upload_id = latest["id"]

    prev_snapshot = get_latest_dispatch_snapshot_map(month)  # None → 尚未发过奖
    xlsx_bytes = export_performance_excel(month, upload_id, prev_snapshot=prev_snapshot)
    filename = f"专项业绩_{month}.xlsx"
    encoded_filename = quote(filename)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="performance_{month}.xlsx"; '
                f"filename*=UTF-8''{encoded_filename}"
            )
        },
    )


@app.post("/api/performance/award-configs")
def save_award_config_api(payload: AwardConfigPayload):
    """保存（新建）一条奖励配置。"""
    from wecom_notice.db import save_award_config
    cfg_id = save_award_config(
        payload.month, payload.award_round,
        payload.rank_from, payload.rank_to,
        payload.metric, payload.prize_name, payload.prize_amount,
        payload.points_weight, payload.gaotao_weight, payload.note,
    )
    return {"ok": True, "id": cfg_id}


@app.get("/api/performance/award-configs/{month}")
def get_award_config_api(month: str, award_round: int = Query(0)):
    """读取奖励配置（award_round=0 表示全部）。"""
    from wecom_notice.db import get_award_configs
    configs = get_award_configs(month, award_round=award_round or None)
    return {"configs": configs}


@app.delete("/api/performance/award-configs/{config_id}")
def delete_award_config_api(config_id: int):
    """删除一条奖励配置。"""
    from wecom_notice.db import delete_award_config
    ok = delete_award_config(config_id)
    if not ok:
        raise HTTPException(status_code=404, detail="配置不存在")
    return {"ok": True}


@app.post("/api/performance/manual-prize")
def manual_performance_prize(payload: ManualPerformancePrizePayload):
    """手动给客户经理发放专项业绩奖励。"""
    month = payload.month.strip()
    manager_name = payload.manager_name.strip()
    prize_name = payload.prize_name.strip()
    prize_amount = int(payload.prize_amount or 0)
    if not month or len(month) != 7:
        raise HTTPException(status_code=400, detail="月份格式应为 YYYY-MM")
    if not manager_name:
        raise HTTPException(status_code=400, detail="请选择客户经理")
    valid_managers = {m.get("name") for m in CUSTOMER_MANAGERS}
    if manager_name not in valid_managers:
        raise HTTPException(status_code=400, detail=f"客户经理「{manager_name}」不在系统名单中，请检查姓名是否完全一致")
    if not prize_name:
        raise HTTPException(status_code=400, detail="请输入奖品名称")
    if prize_amount <= 0:
        raise HTTPException(status_code=400, detail="奖品金额必须大于 0")

    from wecom_notice.db import (
        add_prize_item,
        auto_apply_prizes,
        get_fill_summary_month,
        get_latest_fill_statistics_date,
    )

    raw_note = payload.note.strip() or "专项业绩奖励"
    prize_id = add_prize_item(
        manager_name=manager_name,
        month=month,
        prize_name=prize_name,
        face_amount=prize_amount,
        source="performance",
        source_ref_id=None,
        note=f"手动发放：{raw_note}",
    )

    through_date = get_latest_fill_statistics_date(month)
    total_fine = 0
    for row in get_fill_summary_month(month, through_date=through_date):
        if row.get("manager_name") == manager_name:
            missing_count = int(row.get("missing_count") or 0)
            overtime_count = int(row.get("overtime_count") or 0)
            total_fine = missing_count * 10 + (overtime_count // 5) * 10
            break
    apply_result = auto_apply_prizes(manager_name, month, total_fine) if total_fine > 0 else {"total_covered": 0, "events": []}

    msg = (
        f"[专项业绩] 手动发放奖励｜{month}\n"
        f"· 客户经理：{manager_name}\n"
        f"· 奖励：{prize_name} {prize_amount}元\n"
        f"· 备注：{raw_note}\n"
        f"说明：手动发放的专项业绩奖励已进入客户经理奖品池，并由系统自动用于抵扣扣罚。"
    )
    add_send_log(
        rule_key="performance_manual_prize",
        status="success",
        message_text=msg,
        mentioned=[],
        record_ids=[],
    )
    return {"ok": True, "prize_id": prize_id, "apply_result": apply_result, "message": msg}


@app.post("/api/performance/dispatch")
def dispatch_awards_api(payload: DispatchPayload):
    """
    根据当月已配置的奖励规则 + 最新上传数据自动下发奖励（入库）。
    下发后奖品自动抵扣罚款。不发企业微信通知（由手动通报规则处理）。
    """
    from datetime import date as dt_date

    from wecom_notice.db import (
        get_award_configs, get_performance_uploads, get_performance_stats, dispatch_awards,
    )

    month = payload.month
    award_round = payload.award_round

    configs = get_award_configs(month, award_round=award_round)
    if not configs:
        raise HTTPException(status_code=400, detail="本轮次暂无奖励配置，请先配置")

    uploads = get_performance_uploads(month)
    if not uploads:
        raise HTTPException(status_code=400, detail="本月暂无上传数据，请先上传完美一单")
    chronological_uploads = sorted(uploads, key=lambda u: (u.get("file_date") or "", u.get("uploaded_at") or "", u.get("id") or 0))
    def _upload_by_date(d: str) -> dict[str, Any] | None:
        matches = [u for u in chronological_uploads if (u.get("file_date") or "") == d]
        return matches[-1] if matches else None
    latest = _upload_by_date(payload.right_date) if payload.right_date else chronological_uploads[-1]
    if payload.right_date and not latest:
        raise HTTPException(status_code=400, detail=f"右端点日期 {payload.right_date} 没有对应上传数据")
    left_upload = _upload_by_date(payload.left_date) if payload.left_date else None
    if payload.left_date and not left_upload:
        raise HTTPException(status_code=400, detail=f"左端点日期 {payload.left_date} 没有对应上传数据")
    if payload.left_date and payload.left_date > (latest.get("file_date") or ""):
        raise HTTPException(status_code=400, detail="左端点不能晚于右端点")

    # 下发轮次必须按数据日期递进，避免后来补录的旧数据覆盖到新一轮之后，
    # 造成历史看板出现倒序区间及负新增。
    from wecom_notice.db import get_performance_snapshots
    existing_snapshots = get_performance_snapshots(month)
    previous_dates = [snapshot.get("data_date") or "" for snapshot in existing_snapshots if snapshot.get("award_round", 0) < award_round]
    latest_previous_date = max((value for value in previous_dates if value), default="")
    if latest_previous_date and (latest.get("file_date") or "") < latest_previous_date:
        raise HTTPException(
            status_code=400,
            detail=f"右端点日期不能早于第 {award_round - 1} 轮已下发数据日期 {latest_previous_date}",
        )

    # 本期新增 = 选定右端点累计 - 选定左端点累计；左端点为空表示从本月开始（即从0开始）。
    latest_uid = latest["id"]
    cum_rows = get_performance_stats(month, upload_id=latest_uid)
    left_map = {r["manager_name"]: r for r in get_performance_stats(month, upload_id=left_upload["id"])} if left_upload else {}
    inc_rows_latest = [
        {
            "manager_name": r["manager_name"],
            "inc_points": r["cumulative_points"] - left_map.get(r["manager_name"], {}).get("cumulative_points", 0.0),
            "inc_gaotao": r["cumulative_gaotao"] - left_map.get(r["manager_name"], {}).get("cumulative_gaotao", 0.0),
        }
        for r in cum_rows
    ]

    def _parse_date(value: str) -> dt_date | None:
        try:
            return dt_date.fromisoformat((value or "")[:10])
        except ValueError:
            return None

    latest_date = _parse_date(latest.get("file_date", "")) or _parse_date(payload.dispatch_date) or dt_date.today()
    previous_date = _parse_date(payload.left_date) if payload.left_date else None
    month_days = calendar.monthrange(latest_date.year, latest_date.month)[1]
    incremental_days = max((latest_date - previous_date).days, 1) if previous_date else latest_date.day

    def _score_rows(
        rows: list[dict],
        points_key: str,
        gaotao_key: str,
        points_weight: float,
        gaotao_weight: float,
        days: int,
        denominator_days: int = 31,
    ) -> list[dict]:
        points_target = 2500 * days / denominator_days
        gaotao_target = 14 * days / denominator_days
        base_rows = []
        for row in rows:
            points_rate = min(max(row.get(points_key, 0) / points_target, 0), 1) if points_target else 0
            gaotao_rate = min(max(row.get(gaotao_key, 0) / gaotao_target, 0), 1) if gaotao_target else 0
            completion_score = (points_rate * points_weight + gaotao_rate * gaotao_weight) * 70
            base_rows.append({
                **row,
                "points_rate": points_rate,
                "gaotao_rate": gaotao_rate,
                "completion_score": completion_score,
            })

        total = len(base_rows)
        ranked_by_completion = sorted(base_rows, key=lambda x: x.get("completion_score", 0), reverse=True)
        for idx, row in enumerate(ranked_by_completion):
            rank_score = 30 if total <= 1 else 30 * (total - 1 - idx) / (total - 1)
            row["rank_score"] = rank_score
            row["score"] = row.get("completion_score", 0) + rank_score
        return ranked_by_completion

    def _rank_by_score(rows: list[dict]) -> list[tuple[int, dict]]:
        sorted_rows = sorted(rows, key=lambda x: x.get("score", 0), reverse=True)
        return [(i + 1, r) for i, r in enumerate(sorted_rows)]

    dispatches_to_save: list[dict] = []
    for cfg in configs:
        metric = cfg["metric"]
        rank_from = cfg["rank_from"]
        rank_to = cfg["rank_to"]
        points_weight = cfg.get("points_weight", 0.4)
        gaotao_weight = cfg.get("gaotao_weight", 0.6)

        if metric == "incremental_score":
            month_days = calendar.monthrange(latest_date.year, latest_date.month)[1]
            source_rows = _score_rows(inc_rows_latest, "inc_points", "inc_gaotao", points_weight, gaotao_weight, incremental_days, month_days)
            days = incremental_days
        elif metric == "cumulative_score":
            month_days = calendar.monthrange(latest_date.year, latest_date.month)[1]
            source_rows = _score_rows(cum_rows, "cumulative_points", "cumulative_gaotao", points_weight, gaotao_weight, month_days, month_days)
            days = month_days
        else:
            raise HTTPException(status_code=400, detail=f"不支持的专项业绩奖励类型：{metric}。请使用累计综合或本期新增综合。")

        ranked = _rank_by_score(source_rows)
        for rank, row in ranked:
            if rank_from <= rank <= rank_to:
                dispatches_to_save.append({
                    "manager_name": row["manager_name"],
                    "prize_name": cfg["prize_name"],
                    "prize_amount": cfg["prize_amount"],
                    "metric": metric,
                    "rank_position": rank,
                    "note": (
                        f"综合得分 {row.get('score', 0):.2f}"
                        f"（完成率得分 {row.get('completion_score', 0):.2f}，排名得分 {row.get('rank_score', 0):.2f}，"
                        f"积分系数 {points_weight:g}，高套系数 {gaotao_weight:g}，任务天数 {days}，"
                        f"折算分母 {calendar.monthrange(latest_date.year, latest_date.month)[1]}，"
                        f"右端点 {latest_date.isoformat()}，左端点 {previous_date.isoformat() if previous_date else '本月开始'}）"
                    ),
                })

    if not dispatches_to_save:
        raise HTTPException(status_code=400, detail="根据当前数据和配置，没有符合条件的客户经理")

    ids = dispatch_awards(month, award_round, payload.dispatch_date, dispatches_to_save)

    # 下发完成后保存快照（取当前右端点上传的所有经理累计数据）
    try:
        from wecom_notice.db import save_performance_snapshot
        snapshot_stats = get_performance_stats(month, upload_id=latest_uid)
        save_performance_snapshot(month, award_round, payload.dispatch_date, snapshot_stats, data_date=latest_date.isoformat())
    except Exception:
        pass  # 快照失败不影响下发主流程

    # 下发操作写日志：按累计综合/本期新增综合分组，带统计日期/区间，避免同一客户经理多条奖励看不出来源。
    metric_labels = {"cumulative_score": "累计综合", "incremental_score": "本期新增综合"}
    detail_lines = [f"[专项业绩] 奖励下发｜{month} 第{award_round}轮", ""]
    grouped: dict[str, list[dict]] = {}
    for d in dispatches_to_save:
        grouped.setdefault(d.get("metric", ""), []).append(d)
    for metric in ["cumulative_score", "incremental_score"]:
        rows = grouped.get(metric, [])
        if not rows:
            continue
        if metric == "cumulative_score":
            detail_lines.append(f"{metric_labels[metric]}｜统计日期：截至 {latest_date.isoformat()}")
        else:
            start_label = previous_date.isoformat() if previous_date else month + "-01"
            detail_lines.append(f"{metric_labels[metric]}｜统计区间：{start_label} 至 {latest_date.isoformat()}")
        for d in sorted(rows, key=lambda x: x.get("rank_position", 0)):
            detail_lines.append(f"· 第{d['rank_position']}名 {d['manager_name']}：{d['prize_name']} {d['prize_amount']}元")
        detail_lines.append("")
    detail_lines.append("说明：专项业绩下发奖品已进入客户经理奖品池，并由系统自动用于抵扣扣罚。")
    add_send_log(
        rule_key="performance_dispatch",
        status="success",
        message_text="\n".join(detail_lines).strip(),
        mentioned=[],
        record_ids=[],
        webhook_response=f"dispatch_date={payload.dispatch_date}",
    )
    return {"ok": True, "dispatched": len(ids), "ids": ids}


@app.post("/api/performance/dispatch/{dispatch_id}/revoke")
def revoke_dispatch_api(dispatch_id: int):
    """撤回单条下发记录，同时将对应奖品标记为已撤销。"""
    from wecom_notice.db import revoke_dispatch, get_dispatch_by_id
    # 先取记录信息用于日志
    record = get_dispatch_by_id(dispatch_id)
    ok = revoke_dispatch(dispatch_id)
    if not ok:
        raise HTTPException(status_code=404, detail="下发记录不存在")
    if record:
        add_send_log(
            rule_key="performance_revoke",
            status="success",
            message_text=(
                f"[专项业绩] 撤回奖励 | {record.get('month','')} 第{record.get('award_round','')}轮 "
                f"| {record.get('manager_name','')} {record.get('prize_name','')}（{record.get('prize_amount','')}元）"
            ),
            mentioned=[],
            record_ids=[],
            webhook_response=f"dispatch_id={dispatch_id}",
        )
    return {"ok": True}


@app.get("/api/performance/dispatches/{month}")
def get_dispatches_api(month: str, include_revoked: bool = Query(False)):
    """查询本月下发记录。"""
    from wecom_notice.db import get_dispatches
    return {"dispatches": get_dispatches(month, include_revoked=include_revoked)}


# 前端静态文件（放在所有 API 路由之后，不会覆盖 /api/* 路由）
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
