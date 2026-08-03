"""定时任务调度器 - 管理企业微信通知的定时发送。

使用APScheduler管理所有定时任务，包括：
- 客户经理提醒（18:00-23:00，8个时间点）
- 管理者简洁通报（18:30-21:30，不同经理不同时间）
- 管理者详细通报（22:00）
- 最终数据收集（23:30）
"""

import logging
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from wecom_notice.config import CUSTOMER_MANAGERS, MANAGER_RECIPIENTS
from wecom_notice.db import add_send_log
from wecom_notice.kingsoft_trigger import trigger_kingsoft_data_sync
from wecom_notice.reporter import (
    build_customer_manager_reminder,
    build_final_data_collection,
    build_manager_brief_notice,
    build_manager_detailed_notice,
)
from wecom_notice.sender import send_text

logger = logging.getLogger(__name__)

# 定时规则配置
CUSTOMER_MANAGER_REMINDER_TIMES = [
    "18:00", "18:45", "19:15", "19:45", "20:15", "21:00", "22:00", "23:00"
]

# 金山文档数据同步时间（在提醒前10分钟同步数据）
DATA_SYNC_TIMES = [
    "17:50",  # 第一次提醒前
    "18:35",  # 第二次提醒前
    "19:05",  # 第三次提醒前
    "19:35",  # 第四次提醒前
    "20:05",  # 第五次提醒前
    "20:50",  # 第六次提醒前
    "21:50",  # 第七次提醒前
    "22:50",  # 第八次提醒前
]

# 第一个通报（简洁版）- 张端副经理
BRIEF_NOTICE_ZHANG_TIMES = ["18:30", "19:00", "20:00", "20:30", "21:00", "21:30"]

# 第一个通报（简洁版）- 钟俊杰经理
BRIEF_NOTICE_ZHONG_TIMES = ["19:30", "20:30", "21:00", "21:30"]

# 第二个通报（详细版）- 所有管理者
DETAILED_NOTICE_TIME = "22:00"

# 最终数据收集
FINAL_COLLECTION_TIME = "23:30"


def get_target_date() -> str:
    """获取目标日期（明日）"""
    return (date.today() + timedelta(days=1)).isoformat()


def send_customer_manager_reminders():
    """发送客户经理提醒消息（对所有未达标的客户经理）"""
    target_date = get_target_date()
    logger.info(f"开始发送客户经理提醒，目标日期：{target_date}")

    sent_count = 0
    for manager in CUSTOMER_MANAGERS:
        try:
            report = build_customer_manager_reminder(target_date, manager["name"])

            if not report.get("should_send", False):
                logger.info(f"{manager['name']} 已达标，跳过提醒")
                continue

            # 发送消息
            response = send_text(report["message"], report["recipients"])

            # 记录日志
            add_send_log(
                rule_key="customer_manager_reminder",
                status="success",
                message_text=report["message"],
                mentioned=report["recipients"],
                record_ids=[],
                webhook_response=str(response)
            )

            sent_count += 1
            logger.info(f"成功发送提醒给 {manager['name']}")

        except Exception as e:
            logger.error(f"发送提醒给 {manager['name']} 失败：{e}")
            add_send_log(
                rule_key="customer_manager_reminder",
                status="failed",
                message_text=report.get("message", ""),
                mentioned=report.get("recipients", []),
                record_ids=[],
                error=str(e)
            )

    logger.info(f"客户经理提醒完成，共发送 {sent_count} 条")


def send_brief_notice_to_manager(manager_name: str):
    """发送简洁通报给指定管理者"""
    target_date = get_target_date()
    logger.info(f"开始发送简洁通报给 {manager_name}，目标日期：{target_date}")

    try:
        report = build_manager_brief_notice(target_date)

        if not report.get("should_send", False):
            logger.info(f"全部人员已填报，跳过简洁通报")
            return

        # 只发送给指定管理者
        manager_obj = next((m for m in MANAGER_RECIPIENTS if m["name"] == manager_name), None)
        if not manager_obj:
            logger.warning(f"未找到管理者：{manager_name}")
            return

        recipients = [manager_obj]
        response = send_text(report["message"], recipients)

        add_send_log(
            rule_key=f"brief_notice_{manager_name}",
            status="success",
            message_text=report["message"],
            mentioned=recipients,
            record_ids=[],
            webhook_response=str(response)
        )

        logger.info(f"成功发送简洁通报给 {manager_name}")

    except Exception as e:
        logger.error(f"发送简洁通报给 {manager_name} 失败：{e}")
        add_send_log(
            rule_key=f"brief_notice_{manager_name}",
            status="failed",
            message_text=report.get("message", ""),
            mentioned=[manager_obj] if manager_obj else [],
            record_ids=[],
            error=str(e)
        )


def send_detailed_notice_to_all():
    """发送详细通报给所有管理者"""
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
    """触发金山文档同步数据到服务器"""
    logger.info("触发金山文档数据同步")

    try:
        result = trigger_kingsoft_data_sync()
        logger.info(f"金山文档数据同步触发成功：{result}")

        # 记录同步日志
        add_send_log(
            rule_key="kingsoft_data_sync",
            status="success",
            message_text="触发金山文档数据同步",
            mentioned=[],
            record_ids=[],
            webhook_response=str(result)
        )

    except Exception as e:
        logger.error(f"触发金山文档数据同步失败：{e}")
        add_send_log(
            rule_key="kingsoft_data_sync",
            status="failed",
            message_text="触发金山文档数据同步失败",
            mentioned=[],
            record_ids=[],
            error=str(e)
        )


def start_scheduler(enabled: bool = False) -> BackgroundScheduler:
    """
    启动定时调度器。

    Args:
        enabled: 是否立即启用所有定时任务。默认False，需要手动启用。

    Returns:
        BackgroundScheduler实例
    """
    scheduler = BackgroundScheduler()

    if not enabled:
        logger.info("调度器已创建但未启用定时任务，请在配置后手动启用")
        return scheduler

    # 0. 金山文档数据同步（在提醒前触发）
    for time_str in DATA_SYNC_TIMES:
        hour, minute = time_str.split(":")
        scheduler.add_job(
            sync_kingsoft_data,
            CronTrigger(hour=int(hour), minute=int(minute)),
            id=f"data_sync_{time_str.replace(':', '')}",
            name=f"金山数据同步 {time_str}",
            replace_existing=True
        )

    # 1. 客户经理提醒
    for time_str in CUSTOMER_MANAGER_REMINDER_TIMES:
        hour, minute = time_str.split(":")
        scheduler.add_job(
            send_customer_manager_reminders,
            CronTrigger(hour=int(hour), minute=int(minute)),
            id=f"cm_reminder_{time_str.replace(':', '')}",
            name=f"客户经理提醒 {time_str}",
            replace_existing=True
        )

    # 2. 简洁通报 - 张端
    for time_str in BRIEF_NOTICE_ZHANG_TIMES:
        hour, minute = time_str.split(":")
        scheduler.add_job(
            lambda: send_brief_notice_to_manager("张端"),
            CronTrigger(hour=int(hour), minute=int(minute)),
            id=f"brief_zhang_{time_str.replace(':', '')}",
            name=f"简洁通报-张端 {time_str}",
            replace_existing=True
        )

    # 3. 简洁通报 - 钟俊杰
    for time_str in BRIEF_NOTICE_ZHONG_TIMES:
        hour, minute = time_str.split(":")
        scheduler.add_job(
            lambda: send_brief_notice_to_manager("钟俊杰"),
            CronTrigger(hour=int(hour), minute=int(minute)),
            id=f"brief_zhong_{time_str.replace(':', '')}",
            name=f"简洁通报-钟俊杰 {time_str}",
            replace_existing=True
        )

    # 4. 详细通报 - 所有管理者
    hour, minute = DETAILED_NOTICE_TIME.split(":")
    scheduler.add_job(
        send_detailed_notice_to_all,
        CronTrigger(hour=int(hour), minute=int(minute)),
        id="detailed_notice_all",
        name=f"详细通报-所有管理者 {DETAILED_NOTICE_TIME}",
        replace_existing=True
    )

    # 5. 最终数据收集
    hour, minute = FINAL_COLLECTION_TIME.split(":")
    scheduler.add_job(
        collect_final_data,
        CronTrigger(hour=int(hour), minute=int(minute)),
        id="final_data_collection",
        name=f"最终数据收集 {FINAL_COLLECTION_TIME}",
        replace_existing=True
    )

    scheduler.start()
    logger.info(f"调度器已启动，共 {len(scheduler.get_jobs())} 个定时任务")

    return scheduler


def stop_scheduler(scheduler: BackgroundScheduler):
    """停止调度器"""
    if scheduler:
        scheduler.shutdown()
        logger.info("调度器已停止")
