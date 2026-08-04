"""定时任务调度器 - 管理企业微信通知的定时发送。

使用APScheduler管理所有定时任务。每个发送任务在触发时自动完成完整链路：
  拉取金山文档数据 → 等待数据入库 → 发送企业微信消息 → 更新填报统计表

同一分钟内多个任务触发时，通过5分钟冷却期避免重复同步。
"""

import logging
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from wecom_notice.config import CUSTOMER_MANAGERS, MANAGER_RECIPIENTS
from wecom_notice.db import add_send_log, latest_upload
from wecom_notice.kingsoft_trigger import trigger_kingsoft_data_sync
from wecom_notice.reporter import (
    build_customer_manager_reminder,
    build_final_data_collection,
    build_manager_brief_notice,
    build_manager_detailed_notice,
    build_weekly_report,
    default_target_date,
)
from wecom_notice.sender import send_text

logger = logging.getLogger(__name__)

# 定时规则配置
CUSTOMER_MANAGER_REMINDER_TIMES = [
    "18:15", "18:45", "19:15", "20:15", "20:50", "21:50", "23:00"
]

# 简洁通报时间表：相同时间点的管理者合并为一条消息@多人（按时间升序）
BRIEF_NOTICE_SCHEDULE: dict[str, list[str]] = {
    "18:30": ["张端"],
    "19:00": ["张端", "钟俊杰"],
    "19:30": ["张端", "钟俊杰"],
    "20:00": ["张端"],
    "21:00": ["张端"],
    "21:30": ["张端", "钟俊杰"],
}

# 第二个通报（详细版）- 所有管理者
DETAILED_NOTICE_TIME = "22:00"

# 最终数据收集
FINAL_COLLECTION_TIME = "23:30"


# 通报仅在周一至周五发送（周末不产生预约）
WORKDAY_CRON = "mon-fri"


def get_target_date() -> str:
    """获取目标日期：周一~周四为次日，周五为下周一。"""
    return default_target_date()


# 上次同步完成的时间戳，用于冷却期判断
_last_sync_time: float = 0.0
# 同一分钟内多个任务同时触发时，5分钟内不重复拉取
_SYNC_COOLDOWN = 300


def _sync_with_cooldown():
    """先同步金山数据再继续，5分钟冷却期内跳过重复同步。"""
    global _last_sync_time
    now = time.time()
    if now - _last_sync_time < _SYNC_COOLDOWN:
        logger.info(f"距上次同步不足 {_SYNC_COOLDOWN}s，跳过重复同步")
        return
    _last_sync_time = now
    sync_kingsoft_data()


def send_customer_manager_reminders():
    """发送客户经理提醒消息（对所有未达标的客户经理）"""
    # 在 sync 之前抓触发时刻，确保所有经理消息显示同一个时间点（如18:15）
    round_notice_time = datetime.now().strftime("%H:%M")
    _sync_with_cooldown()
    target_date = get_target_date()
    logger.info(f"开始发送客户经理提醒，目标日期：{target_date}，本轮时间：{round_notice_time}")

    sent_count = 0
    for manager in CUSTOMER_MANAGERS:
        try:
            report = build_customer_manager_reminder(target_date, manager["name"], notice_time=round_notice_time)
            if not report.get("should_send", False):
                logger.info(f"{manager['name']} 已达标，跳过提醒")
                continue
            response = send_text(report["message"], report["recipients"])
            add_send_log(
                rule_key="customer_manager_reminder",
                status="success",
                message_text=report["message"],
                mentioned=report["recipients"],
                record_ids=[],
                webhook_response=str(response),
            )
            sent_count += 1
            logger.info(f"成功发送提醒给 {manager['name']}")
            time.sleep(60)
        except Exception as e:
            logger.error(f"发送提醒给 {manager['name']} 失败：{e}")
            add_send_log(
                rule_key="customer_manager_reminder",
                status="failed",
                message_text=report.get("message", ""),
                mentioned=report.get("recipients", []),
                record_ids=[],
                error=str(e),
            )

    if sent_count == 0:
        add_send_log(
            rule_key="customer_manager_reminder",
            status="success",
            message_text=f"客户经理提醒完成：本轮无需发送（目标日期 {target_date} 的人员均已达标）",
            mentioned=[],
            record_ids=[],
            webhook_response="no_reminder_needed",
        )
    logger.info(f"客户经理提醒完成，共发送 {sent_count} 条")


def send_brief_notice_to_managers(manager_names: list[str]):
    """发送简洁通报给指定管理者（支持同时@多人）"""
    _sync_with_cooldown()
    target_date = get_target_date()
    names_str = "、".join(manager_names)
    logger.info(f"开始发送简洁通报给 {names_str}，目标日期：{target_date}")

    try:
        report = build_manager_brief_notice(target_date)

        if not report.get("should_send", False):
            logger.info("全部人员已填报，跳过简洁通报")
            return

        # 筛选指定的管理者
        recipients = [m for m in MANAGER_RECIPIENTS if m["name"] in manager_names]
        if not recipients:
            logger.warning(f"未找到管理者：{manager_names}")
            return

        response = send_text(report["message"], recipients)

        add_send_log(
            rule_key=f"brief_notice_{'_'.join(manager_names)}",
            status="success",
            message_text=report["message"],
            mentioned=recipients,
            record_ids=[],
            webhook_response=str(response),
        )
        logger.info(f"成功发送简洁通报给 {names_str}")

    except Exception as e:
        logger.error(f"发送简洁通报给 {names_str} 失败：{e}")
        recipients = [m for m in MANAGER_RECIPIENTS if m["name"] in manager_names]
        add_send_log(
            rule_key=f"brief_notice_{'_'.join(manager_names)}",
            status="failed",
            message_text=report.get("message", ""),
            mentioned=recipients,
            record_ids=[],
            error=str(e),
        )


def send_detailed_notice_to_all():
    """发送详细通报给所有管理者"""
    _sync_with_cooldown()
    target_date = get_target_date()
    logger.info(f"开始发送详细通报，目标日期：{target_date}")

    try:
        report = build_manager_detailed_notice(target_date)

        if not report.get("should_send", False):
            logger.info(f"详细通报不需要发送")
            return

        response = send_text(report["message"], report["recipients"])

        add_send_log(
            rule_key="detailed_notice_all",
            status="success",
            message_text=report["message"],
            mentioned=report["recipients"],
            record_ids=[],
            webhook_response=str(response)
        )

        logger.info(f"成功发送详细通报给所有管理者")

    except Exception as e:
        logger.error(f"发送详细通报失败：{e}")
        add_send_log(
            rule_key="detailed_notice_all",
            status="failed",
            message_text=report.get("message", ""),
            mentioned=report.get("recipients", []),
            record_ids=[],
            error=str(e)
        )


def send_weekly_report():
    """发送周通报（本月预约填报情况汇总）。
    计划：周三 12:15 / 周日 12:00 各触发一次。
    """
    logger.info("开始发送周通报")
    try:
        result = build_weekly_report()
        if result["should_send"]:
            response = send_text(result["message"], result["recipients"])
            add_send_log(
                rule_key="weekly_report",
                status="success" if response.get("errcode") == 0 else "failed",
                message_text=result["message"],
                mentioned=result["recipients"],
                record_ids=[],
                webhook_response=str(response),
            )
            logger.info("周通报发送完成")
        else:
            logger.info("周通报无需发送")
    except Exception as e:
        logger.error(f"发送周通报失败：{e}")
        add_send_log(
            rule_key="weekly_report",
            status="failed",
            message_text="",
            mentioned=[],
            record_ids=[],
            error=str(e),
        )


def collect_final_data():
    """最终数据收集（23:30），更新统计表"""
    target_date = get_target_date()
    logger.info(f"开始最终数据收集，目标日期：{target_date}")

    try:
        result = build_final_data_collection(target_date)
        logger.info(f"数据收集完成：{result['results']}")

        # 记录收集结果
        add_send_log(
            rule_key="final_data_collection",
            status="success",
            message_text=f"数据收集完成，处理 {len(result['results'])} 位客户经理",
            mentioned=[],
            record_ids=[],
            webhook_response=str(result)
        )

    except Exception as e:
        logger.error(f"最终数据收集失败：{e}")
        add_send_log(
            rule_key="final_data_collection",
            status="failed",
            message_text="数据收集失败",
            mentioned=[],
            record_ids=[],
            error=str(e)
        )


def sync_kingsoft_data():
    """触发金山文档数据同步，阻塞等待数据写入服务器后再返回。

    流程：
    1. 记录当前 latest_upload 时间戳
    2. 向金山文档发送 webhook，触发 AirScript 上传
    3. 轮询 latest_upload，直到时间戳更新（数据已写入）或超时
    4. 数据到位后立即更新填报统计表
    """
    logger.info("触发金山文档数据同步（同步模式）")

    before = latest_upload()

    try:
        result = trigger_kingsoft_data_sync()
        logger.info(f"金山文档数据同步触发成功：{result}")
    except Exception as e:
        logger.error(f"触发金山文档数据同步失败：{e}")
        add_send_log(
            rule_key="kingsoft_data_sync",
            status="failed",
            message_text="触发金山文档数据同步失败",
            mentioned=[],
            record_ids=[],
            error=str(e),
        )
        return

    # 轮询等待数据写入（最多等 8 分钟，每 10 秒检查一次）
    _POLL_INTERVAL = 10
    _TIMEOUT = 480
    elapsed = 0
    while elapsed < _TIMEOUT:
        time.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL
        after = latest_upload()
        if after != before:
            logger.info(f"金山数据已到达，上传时间：{after}，等待耗时 {elapsed}s")
            break
    else:
        logger.warning(f"等待金山数据超时（{_TIMEOUT}s），继续执行后续任务")

    add_send_log(
        rule_key="kingsoft_data_sync",
        status="success",
        message_text="触发金山文档数据同步",
        mentioned=[],
        record_ids=[],
        webhook_response=str(result),
    )

    # 数据已更新，立即刷新填报统计表
    target_date = get_target_date()
    try:
        stats_result = build_final_data_collection(target_date)
        logger.info(f"统计表已更新：处理 {len(stats_result['results'])} 位客户经理")
        add_send_log(
            rule_key="final_data_collection",
            status="success",
            message_text=f"统计表更新完成，处理 {len(stats_result['results'])} 位客户经理",
            mentioned=[],
            record_ids=[],
            webhook_response=str(stats_result),
        )
    except Exception as e:
        logger.error(f"统计表更新失败：{e}")
        add_send_log(
            rule_key="final_data_collection",
            status="failed",
            message_text="统计表更新失败",
            mentioned=[],
            record_ids=[],
            error=str(e),
        )


# 周末数据同步时间点（周六、周日均执行；仅入库，不影响填报统计指标）
WEEKEND_SYNC_TIMES = ["12:00", "18:00", "22:00", "23:30"]


def sync_kingsoft_data_only():
    """周末专用（周六/周日）：仅触发金山文档数据同步入库，不更新 fill_statistics。

    周六/周日填写的预约记录会被拉取并存入 visit_records，
    但不判断准时/超时/漏填，不影响任何统计指标。
    所有统计（准时/超时/漏填）只在周一~周五的 23:30 由 collect_final_data 执行。
    """
    logger.info("周末数据同步：触发金山文档数据入库（不更新统计指标）")

    before = latest_upload()
    try:
        result = trigger_kingsoft_data_sync()
        logger.info(f"周日金山数据同步触发成功：{result}")
    except Exception as e:
        logger.error(f"周日金山数据同步失败：{e}")
        add_send_log(
            rule_key="sunday_kingsoft_sync",
            status="failed",
            message_text="周日金山数据同步失败",
            mentioned=[],
            record_ids=[],
            error=str(e),
        )
        return

    # 轮询等待数据写入（最多8分钟）
    _POLL_INTERVAL = 10
    _TIMEOUT = 480
    elapsed = 0
    while elapsed < _TIMEOUT:
        time.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL
        after = latest_upload()
        if after != before:
            logger.info(f"周日同步：金山数据已到达，上传时间：{after}，耗时 {elapsed}s")
            break
    else:
        logger.warning(f"周日同步：等待金山数据超时（{_TIMEOUT}s）")

    add_send_log(
        rule_key="sunday_kingsoft_sync",
        status="success",
        message_text="周日金山数据同步完成（仅入库，不更新统计指标）",
        mentioned=[],
        record_ids=[],
        webhook_response=str(result),
    )
    # 注意：此处故意不调用 build_final_data_collection，
    # 周六/周日填写的预约不计入准时/超时统计，必须周五填才算。


def start_scheduler(enabled: bool = False) -> BackgroundScheduler:
    """
    启动定时调度器。

    Args:
        enabled: 是否立即启用所有定时任务。默认False，需要手动启用。

    Returns:
        BackgroundScheduler实例
    """
    # misfire_grace_time：服务在触发点前后重启时，默认只有 1 秒宽限，任务会被直接丢弃。
    # 给 10 分钟宽限，重启刚好压到时间点也能补发；coalesce 保证只补最后一次，不会连发。
    scheduler = BackgroundScheduler(job_defaults={
        "misfire_grace_time": 600,
        "coalesce": True,
        "max_instances": 1,
    })

    if not enabled:
        logger.info("调度器已创建但未启用定时任务，请在配置后手动启用")
        return scheduler

    # 1. 客户经理提醒（周一~周五）
    for time_str in CUSTOMER_MANAGER_REMINDER_TIMES:
        hour, minute = time_str.split(":")
        scheduler.add_job(
            send_customer_manager_reminders,
            CronTrigger(day_of_week=WORKDAY_CRON, hour=int(hour), minute=int(minute)),
            id=f"cm_reminder_{time_str.replace(':', '')}",
            name=f"客户经理提醒 {time_str}",
            replace_existing=True
        )

    # 2. 简洁通报 - 按时间表@对应管理者（周一~周五）
    for time_str, manager_names in BRIEF_NOTICE_SCHEDULE.items():
        hour, minute = time_str.split(":")
        names_label = "&".join(manager_names)
        scheduler.add_job(
            send_brief_notice_to_managers,
            CronTrigger(day_of_week=WORKDAY_CRON, hour=int(hour), minute=int(minute)),
            args=[manager_names],
            id=f"brief_{'_'.join(manager_names)}_{time_str.replace(':', '')}",
            name=f"简洁通报-{names_label} {time_str}",
            replace_existing=True
        )

    # 4. 详细通报 - 所有管理者（周一~周五）
    hour, minute = DETAILED_NOTICE_TIME.split(":")
    scheduler.add_job(
        send_detailed_notice_to_all,
        CronTrigger(day_of_week=WORKDAY_CRON, hour=int(hour), minute=int(minute)),
        id="detailed_notice_all",
        name=f"详细通报-所有管理者 {DETAILED_NOTICE_TIME}",
        replace_existing=True
    )

    # 5. 最终数据收集（周一~周五）
    hour, minute = FINAL_COLLECTION_TIME.split(":")
    scheduler.add_job(
        collect_final_data,
        CronTrigger(day_of_week=WORKDAY_CRON, hour=int(hour), minute=int(minute)),
        id="final_data_collection",
        name=f"最终数据收集 {FINAL_COLLECTION_TIME}",
        replace_existing=True
    )

    # 6. 周通报 - 周三 12:15
    scheduler.add_job(
        send_weekly_report,
        CronTrigger(day_of_week="wed", hour=12, minute=15),
        id="weekly_report_wed",
        name="周通报-周三 12:15",
        replace_existing=True,
    )

    # 7. 周通报 - 周日 12:00
    scheduler.add_job(
        send_weekly_report,
        CronTrigger(day_of_week="sun", hour=12, minute=0),
        id="weekly_report_sun",
        name="周通报-周日 12:00",
        replace_existing=True,
    )

    # 8. 周末数据同步（周六/周日均执行；仅入库，不影响统计指标）
    for time_str in WEEKEND_SYNC_TIMES:
        hour, minute = time_str.split(":")
        scheduler.add_job(
            sync_kingsoft_data_only,
            CronTrigger(day_of_week="sat,sun", hour=int(hour), minute=int(minute)),
            id=f"weekend_sync_{time_str.replace(':', '')}",
            name=f"周末数据同步 {time_str}",
            replace_existing=True,
        )

    scheduler.start()
    logger.info(f"调度器已启动，共 {len(scheduler.get_jobs())} 个定时任务")

    return scheduler


def stop_scheduler(scheduler: BackgroundScheduler):
    """停止调度器"""
    if scheduler:
        scheduler.shutdown()
        logger.info("调度器已停止")
