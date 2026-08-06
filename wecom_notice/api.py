import logging
import base64
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
    message = """📋【预约填报管理规则】

━━━━━━ ⏰ 填报时间规则 ━━━━━━

✅ 准时填报：19:30 前完成
⏱️ 超时填报：19:30 - 23:30 之间完成
❌ 漏填：23:30 前未完成

━━━━━━ ☕ 下午茶基金 ━━━━━━

💰 扣款标准：
   · 漏填：10 元/次
   · 超时：每累计 5 次扣 10 元
   · 按自然月统计，次月清零

🎴 天命赦令减免：
   · 抽签奖品可抵扣罚款
   · 不改变超时/漏填次数记录
   · 减免额度：5-30 元不等

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

准时填报，好运相伴！🍀"""

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
    metric: str = "points"    # "points" | "gaotao"
    prize_name: str
    prize_amount: int
    note: str = ""


class DispatchPayload(BaseModel):
    month: str
    award_round: int = 1
    dispatch_date: str        # YYYY-MM-DD


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

    return {"ok": True, "upload_id": upload_id, "file_date": file_date,
            "manager_count": len(parsed["stats"])}


@app.get("/api/performance/stats/{month}")
def performance_stats(month: str):
    """返回本月各轮次的累计 + 增量数据，以及本月已下发的奖励明细。"""
    from wecom_notice.performance import compute_incremental_stats
    from wecom_notice.db import get_dispatches, get_award_configs

    from wecom_notice.db import get_performance_snapshots
    result = compute_incremental_stats(month)
    dispatches = get_dispatches(month, include_revoked=True)
    configs = get_award_configs(month)
    snapshots = get_performance_snapshots(month)
    return {
        "month": month,
        "uploads": result["uploads"],
        "cumulative": result["cumulative"],
        "incremental": result["incremental"],
        "dispatches": dispatches,
        "award_configs": configs,
        "snapshots": snapshots,
    }


@app.get("/api/performance/stats/{month}/export")
def performance_stats_export(month: str, upload_id: int = Query(0)):
    """下载专项业绩 Excel。新增列基准：本月最新一次下发奖励快照；首次发奖前显示 "-"。"""
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
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/performance/award-configs")
def save_award_config_api(payload: AwardConfigPayload):
    """保存（新建）一条奖励配置。"""
    from wecom_notice.db import save_award_config
    cfg_id = save_award_config(
        payload.month, payload.award_round,
        payload.rank_from, payload.rank_to,
        payload.metric, payload.prize_name, payload.prize_amount, payload.note,
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


@app.post("/api/performance/dispatch")
def dispatch_awards_api(payload: DispatchPayload):
    """
    根据当月已配置的奖励规则 + 最新上传数据自动下发奖励（入库）。
    下发后奖品自动抵扣罚款。不发企业微信通知（由手动通报规则处理）。
    """
    from wecom_notice.db import (
        get_award_configs, get_latest_performance_upload,
        get_performance_stats, dispatch_awards,
    )
    from wecom_notice.performance import compute_incremental_stats

    month = payload.month
    award_round = payload.award_round

    configs = get_award_configs(month, award_round=award_round)
    if not configs:
        raise HTTPException(status_code=400, detail="本轮次暂无奖励配置，请先配置")

    latest = get_latest_performance_upload(month)
    if not latest:
        raise HTTPException(status_code=400, detail="本月暂无上传数据，请先上传完美一单")

    # 根据配置规则计算各人应得奖励
    inc_result = compute_incremental_stats(month)
    incremental = inc_result["incremental"]

    # 找到本轮次之前的最新上传（用于计算增量）
    # 若第一轮用累计，否则用最近两次上传的增量
    latest_uid = latest["id"]
    cum_rows = get_performance_stats(month, upload_id=latest_uid)
    inc_rows_latest = incremental.get(latest_uid, [])

    def _rank_by_metric(rows: list[dict], metric_key: str) -> list[tuple[int, dict]]:
        sorted_rows = sorted(rows, key=lambda x: x.get(metric_key, 0), reverse=True)
        return [(i + 1, r) for i, r in enumerate(sorted_rows)]

    dispatches_to_save: list[dict] = []
    for cfg in configs:
        metric = cfg["metric"]
        rank_from = cfg["rank_from"]
        rank_to = cfg["rank_to"]

        # 第一轮用累计，后续用增量
        if award_round == 1:
            metric_key = "cumulative_points" if metric == "points" else "cumulative_gaotao"
            source_rows = cum_rows
        else:
            metric_key = "inc_points" if metric == "points" else "inc_gaotao"
            source_rows = inc_rows_latest

        ranked = _rank_by_metric(source_rows, metric_key)
        for rank, row in ranked:
            if rank_from <= rank <= rank_to:
                dispatches_to_save.append({
                    "manager_name": row["manager_name"],
                    "prize_name": cfg["prize_name"],
                    "prize_amount": cfg["prize_amount"],
                    "metric": metric,
                    "rank_position": rank,
                })

    if not dispatches_to_save:
        raise HTTPException(status_code=400, detail="根据当前数据和配置，没有符合条件的客户经理")

    ids = dispatch_awards(month, award_round, payload.dispatch_date, dispatches_to_save)

    # 下发完成后保存快照（取当前最新上传的所有经理累计数据）
    try:
        from wecom_notice.db import save_performance_snapshot
        snapshot_stats = get_performance_stats(month, upload_id=latest_uid)
        save_performance_snapshot(month, award_round, payload.dispatch_date, snapshot_stats)
    except Exception:
        pass  # 快照失败不影响下发主流程

    return {"ok": True, "dispatched": len(ids), "ids": ids}


@app.post("/api/performance/dispatch/{dispatch_id}/revoke")
def revoke_dispatch_api(dispatch_id: int):
    """撤回单条下发记录，同时将对应奖品标记为已撤销。"""
    from wecom_notice.db import revoke_dispatch
    ok = revoke_dispatch(dispatch_id)
    if not ok:
        raise HTTPException(status_code=404, detail="下发记录不存在")
    return {"ok": True}


@app.get("/api/performance/dispatches/{month}")
def get_dispatches_api(month: str, include_revoked: bool = Query(False)):
    """查询本月下发记录。"""
    from wecom_notice.db import get_dispatches
    return {"dispatches": get_dispatches(month, include_revoked=include_revoked)}


# 前端静态文件（放在所有 API 路由之后，不会覆盖 /api/* 路由）
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
