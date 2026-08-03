from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from wecom_notice.config import CUSTOMER_MANAGERS, GAOZHUANG_STAFF, MANAGER_RECIPIENTS, ZHIYUN_ENGINEERS
from wecom_notice.db import (
    add_reminder_log,
    get_fill_statistics,
    get_manager_history_counts,
    get_records,
    get_records_by_date_range,
    get_reminder_logs,
    increment_reminder_count,
)


def default_target_date() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def recipients_for(policy: dict[str, Any], manager_names: list[str]) -> list[dict[str, str]]:
    target = policy.get("target", "customer_managers")
    recipients: list[dict[str, str]] = []
    if target in {"customer_managers", "customer_managers_and_management"}:
        names = set(manager_names)
        recipients.extend(person for person in CUSTOMER_MANAGERS if person["name"] in names)
    if target in {"management", "customer_managers_and_management"}:
        recipients.extend(MANAGER_RECIPIENTS)
    return recipients


# ====== 新增通报构建器 ======


def build_customer_manager_reminder(target_date: str, manager_name: str, required: int = 2) -> dict[str, Any]:
    """
    客户经理提醒消息：单独@客户经理，显示已填户数、超时/漏填历史、今日提醒次数。
    填了2户及以上的不返回消息（should_send=False）。
    实习期人员（exclude_reminder=True）不发送提醒。
    """
    # 检查是否需要排除提醒
    manager_obj = next((m for m in CUSTOMER_MANAGERS if m["name"] == manager_name), None)
    if manager_obj and manager_obj.get("exclude_reminder", False):
        return {"message": "", "recipients": [], "should_send": False, "manager_name": manager_name, "excluded": True}

    records = get_records(appointment_date=target_date, manager=manager_name)
    current_count = len(records)

    if current_count >= required:
        return {"message": "", "recipients": [], "should_send": False, "manager_name": manager_name}

    # 获取历史超时和漏填次数
    history = get_manager_history_counts(manager_name, target_date)
    overtime_count = history["overtime_count"]
    missing_count = history["missing_count"]

    # 获取今日已提醒次数并递增
    reminder_seq = increment_reminder_count(target_date, manager_name)

    # 记录提醒日志
    add_reminder_log(target_date, manager_name, current_count, reminder_seq, overtime_count, missing_count)

    # 构建消息
    gap = required - current_count
    emojis = ["📋", "⏰", "📝", "✍️", "📊", "🔔", "💼", "📌"]
    emoji = emojis[(reminder_seq - 1) % len(emojis)]

    lines = [
        f"{emoji} @{manager_name}",
        "",
        f"明日预约填报提醒（第{reminder_seq}次）",
        f"📅 日期：{target_date}",
        f"✅ 已填：{current_count} 户",
        f"⚠️ 还需：{gap} 户",
    ]

    if overtime_count > 0 or missing_count > 0:
        lines.append("")
        lines.append("📊 历史记录：")
        if overtime_count > 0:
            lines.append(f"   ⏱️ 超时填报：{overtime_count} 次")
        if missing_count > 0:
            lines.append(f"   ❌ 漏填：{missing_count} 次")

    lines.extend([
        "",
        "💡 温馨提示：请尽快完成填报，确保明日工作顺利开展~"
    ])

    manager_obj = next((m for m in CUSTOMER_MANAGERS if m["name"] == manager_name), None)
    recipients = [manager_obj] if manager_obj else []

    return {
        "message": "\n".join(lines),
        "recipients": recipients,
        "should_send": True,
        "manager_name": manager_name,
        "current_count": current_count,
        "reminder_seq": reminder_seq,
    }


def build_manager_brief_notice(target_date: str, required: int = 2) -> dict[str, Any]:
    """
    第一个通报（简洁版）：谁填了，谁没填。
    未填的放前面，用❌标红。如果全部人员都填了就不发送（should_send=False）。
    实习期人员（exclude_reminder=True）不计入统计。
    """
    records = get_records(appointment_date=target_date)
    counts = Counter(record["manager_name"] for record in records if record["manager_name"])

    filled = []
    not_filled = []

    for manager in CUSTOMER_MANAGERS:
        # 跳过实习期人员
        if manager.get("exclude_reminder", False):
            continue

        count = counts[manager["name"]]
        if count >= required:
            filled.append(f"✅ {manager['name']}：已填报 {count} 户")
        else:
            not_filled.append(f"❌ {manager['name']}：已填报 {count} 户，还差 {required - count} 户")

    if not not_filled:
        return {"message": "", "recipients": [], "should_send": False, "all_filled": True}

    current_time = datetime.now().strftime("%H:%M")
    lines = [
        f"【预约填报提醒】{target_date}",
        f"⏰ 当前时间：{current_time}",
        "",
        "⚠️ 未完成填报：",
        *not_filled,
    ]

    if filled:
        lines.extend([
            "",
            "✅ 已完成填报：",
            *filled
        ])

    return {
        "message": "\n".join(lines),
        "recipients": MANAGER_RECIPIENTS,
        "should_send": True,
        "all_filled": False,
        "not_filled_count": len(not_filled),
    }


def build_manager_detailed_notice(target_date: str, required: int = 2) -> dict[str, Any]:
    """
    第二个通报（详细版）：包含今日情况和累计情况。
    - 今日情况：没填的在前面，填了的显示拜访客户和预约交付人员
    - 累计情况：漏填、超时、准时，做得好的在前面，加emoji
    实习期人员（exclude_reminder=True）不计入统计。
    """
    records = get_records(appointment_date=target_date)
    counts = Counter(record["manager_name"] for record in records if record["manager_name"])

    # 今日情况
    not_filled_today = []
    filled_today = []

    for manager in CUSTOMER_MANAGERS:
        # 跳过实习期人员
        if manager.get("exclude_reminder", False):
            continue

        count = counts[manager["name"]]
        if count < required:
            not_filled_today.append(f"❌ {manager['name']}：已填报 {count} 户，还差 {required - count} 户")
        else:
            manager_records = [r for r in records if r["manager_name"] == manager["name"]]
            details = []
            for r in manager_records[:3]:  # 最多显示3条
                company = r["company_name"] or "未填写企业"
                delivery_staff = r["delivery_staff_name"] or ""

                # 判断交付类型：高装/智云/未指定
                if delivery_staff in [g["name"] for g in GAOZHUANG_STAFF]:
                    delivery_type = "高装"
                elif delivery_staff in [z["name"] for z in ZHIYUN_ENGINEERS]:
                    delivery_type = "智云"
                else:
                    delivery_type = "未指定"

                details.append(f"    · {company}（{delivery_type}：{delivery_staff or '无'}）")
            if len(manager_records) > 3:
                details.append(f"    ... 还有 {len(manager_records) - 3} 户")

            filled_today.append(f"✅ {manager['name']}：{count} 户")
            filled_today.extend(details)

    # 累计情况统计
    today_str = date.today().isoformat()
    all_stats = get_fill_statistics(end_date=today_str)

    on_time_managers = {}
    overtime_managers = {}
    missing_managers = {}

    for stat in all_stats:
        mgr = stat["manager_name"]
        status = stat["fill_status"]
        if status == "on_time":
            on_time_managers[mgr] = on_time_managers.get(mgr, 0) + 1
        elif status == "overtime":
            overtime_managers[mgr] = overtime_managers.get(mgr, 0) + 1
        elif status == "missing":
            missing_managers[mgr] = missing_managers.get(mgr, 0) + 1

    # 构建消息
    current_time = datetime.now().strftime("%H:%M")
    lines = [
        f"【明日预约详细通报】{target_date}",
        f"⏰ 通报时间：{current_time}",
        "",
        "━━━━━━ 📊 今日填报情况 ━━━━━━",
    ]

    if not_filled_today:
        lines.append("")
        lines.append("⚠️ 未完成填报：")
        lines.extend(not_filled_today)

    if filled_today:
        lines.append("")
        lines.append("✅ 已完成填报：")
        lines.extend(filled_today)

    lines.extend([
        "",
        "━━━━━━ 📈 累计填报情况 ━━━━━━",
    ])

    # 准时填报（做得好的）
    if on_time_managers:
        sorted_on_time = sorted(on_time_managers.items(), key=lambda x: x[1], reverse=True)
        lines.append("")
        lines.append("👍 准时填报（19:30前完成）：")
        for mgr, cnt in sorted_on_time:
            lines.append(f"   🎉 {mgr}：{cnt} 次")

    # 超时填报
    if overtime_managers:
        sorted_overtime = sorted(overtime_managers.items(), key=lambda x: x[1], reverse=True)
        lines.append("")
        lines.append("⏱️ 超时填报（19:30-23:30）：")
        for mgr, cnt in sorted_overtime:
            lines.append(f"   {mgr}：{cnt} 次")

    # 漏填情况
    if missing_managers:
        sorted_missing = sorted(missing_managers.items(), key=lambda x: x[1], reverse=True)
        lines.append("")
        lines.append("❌ 漏填情况（23:30未完成）：")
        for mgr, cnt in sorted_missing:
            lines.append(f"   {mgr}：{cnt} 次")

    if not on_time_managers and not overtime_managers and not missing_managers:
        lines.append("")
        lines.append("暂无累计统计数据")

    return {
        "message": "\n".join(lines),
        "recipients": MANAGER_RECIPIENTS,
        "should_send": True,
        "today_summary": {
            "not_filled": len(not_filled_today),
            "filled": len(filled_today),
        },
        "cumulative_summary": {
            "on_time": len(on_time_managers),
            "overtime": len(overtime_managers),
            "missing": len(missing_managers),
        },
    }


def build_final_data_collection(target_date: str, required: int = 2) -> dict[str, Any]:
    """
    23:30最终数据收集：判断每位客户经理的填报状态并更新统计表。
    不发送消息，仅用于数据整理。
    实习期人员（exclude_reminder=True）不计入统计。
    """
    from wecom_notice.db import upsert_fill_statistics

    records = get_records(appointment_date=target_date)
    counts = Counter(record["manager_name"] for record in records if record["manager_name"])

    # 获取今日所有提醒日志，判断最后一次填报完成的时间
    today_str = date.today().isoformat()

    results = []
    for manager in CUSTOMER_MANAGERS:
        # 跳过实习期人员
        if manager.get("exclude_reminder", False):
            continue

        count = counts[manager["name"]]
        mgr_name = manager["name"]

        if count < required:
            # 漏填
            upsert_fill_statistics(today_str, mgr_name, "missing", "", count)
            results.append({"manager": mgr_name, "status": "missing", "count": count})
        else:
            # 判断是准时还是超时（根据记录的uploaded_at时间）
            mgr_records = [r for r in records if r["manager_name"] == mgr_name]
            # 简化处理：如果在19:30前已经有至少2条记录的uploaded_at，则为准时
            # 这里使用最后一条记录的uploaded_at作为填报完成时间
            if mgr_records:
                last_record = max(mgr_records, key=lambda r: r["uploaded_at"])
                fill_time = last_record["uploaded_at"]

                # 解析时间判断是否在19:30前
                try:
                    fill_dt = datetime.fromisoformat(fill_time)
                    cutoff_time = datetime.combine(fill_dt.date(), datetime.strptime("19:30", "%H:%M").time())

                    if fill_dt <= cutoff_time and count >= required:
                        status = "on_time"
                    else:
                        status = "overtime"
                except Exception:
                    status = "overtime"  # 解析失败默认为超时

                upsert_fill_statistics(today_str, mgr_name, status, fill_time, count)
                results.append({"manager": mgr_name, "status": status, "count": count, "fill_time": fill_time})
            else:
                # 理论上不会到这里
                upsert_fill_statistics(today_str, mgr_name, "missing", "", count)
                results.append({"manager": mgr_name, "status": "missing", "count": count})

    return {
        "message": "",
        "recipients": [],
        "should_send": False,
        "results": results,
        "collection_time": datetime.now().isoformat(),
    }


# ====== 累计统计报表 ======


def build_cumulative_statistics(start_date: str = "", end_date: str = "") -> dict[str, Any]:
    """
    生成累计统计数据，用于Excel导出和图片生成。
    返回格式：{"on_time": [...], "overtime": [...], "missing": [...], "summary": {...}}
    """
    if not end_date:
        end_date = date.today().isoformat()
    if not start_date:
        # 默认统计最近30天
        start_date = (date.today() - timedelta(days=30)).isoformat()

    all_stats = get_fill_statistics(start_date, end_date)
    if not all_stats:
        all_stats = build_fill_statistics_from_records(start_date, end_date)

    # 按客户经理分组统计
    manager_stats = {}
    for stat in all_stats:
        mgr = stat["manager_name"]
        if mgr not in manager_stats:
            manager_stats[mgr] = {"on_time": [], "overtime": [], "missing": []}

        status = stat["fill_status"]
        if status in manager_stats[mgr]:
            manager_stats[mgr][status].append({
                "date": stat["date"],
                "fill_time": stat["fill_time"],
                "fill_count": stat["fill_count"],
                "reminder_count": stat["reminder_count"],
            })

    # 整理为输出格式
    on_time_list = []
    overtime_list = []
    missing_list = []

    for mgr, stats in manager_stats.items():
        if stats["on_time"]:
            on_time_list.append({
                "manager_name": mgr,
                "dates": [s["date"] for s in stats["on_time"]],
                "count": len(stats["on_time"]),
                "details": stats["on_time"],
            })
        if stats["overtime"]:
            overtime_list.append({
                "manager_name": mgr,
                "dates": [s["date"] for s in stats["overtime"]],
                "count": len(stats["overtime"]),
                "details": stats["overtime"],
            })
        if stats["missing"]:
            missing_list.append({
                "manager_name": mgr,
                "dates": [s["date"] for s in stats["missing"]],
                "count": len(stats["missing"]),
                "details": stats["missing"],
            })

    # 按次数降序排序（准时的做得好的在前面，漏填的次数多的在前面）
    on_time_list.sort(key=lambda x: x["count"], reverse=True)
    overtime_list.sort(key=lambda x: x["count"], reverse=True)
    missing_list.sort(key=lambda x: x["count"], reverse=True)

    # 计算汇总统计
    total_days = len(set(s["date"] for s in all_stats))
    total_records = len(all_stats)
    on_time_count = sum(x["count"] for x in on_time_list)
    overtime_count = sum(x["count"] for x in overtime_list)
    missing_count = sum(x["count"] for x in missing_list)

    summary = {
        "start_date": start_date,
        "end_date": end_date,
        "total_days": total_days,
        "total_records": total_records,
        "on_time_count": on_time_count,
        "overtime_count": overtime_count,
        "missing_count": missing_count,
        "on_time_rate": round(on_time_count / total_records, 3) if total_records > 0 else 0,
        "overtime_rate": round(overtime_count / total_records, 3) if total_records > 0 else 0,
        "missing_rate": round(missing_count / total_records, 3) if total_records > 0 else 0,
    }

    details_by_manager: dict[str, dict[str, Any]] = {}
    for manager in CUSTOMER_MANAGERS:
        details_by_manager[manager["name"]] = {
            "manager_name": manager["name"],
            "team": manager.get("team", ""),
            "on_time": 0,
            "overtime": 0,
            "missing": 0,
        }
    for stat in all_stats:
        mgr = stat["manager_name"]
        if mgr not in details_by_manager:
            details_by_manager[mgr] = {"manager_name": mgr, "team": "", "on_time": 0, "overtime": 0, "missing": 0}
        status = stat["fill_status"]
        if status in {"on_time", "overtime", "missing"}:
            details_by_manager[mgr][status] += 1

    details = sorted(
        details_by_manager.values(),
        key=lambda x: (-(x["on_time"] + x["overtime"] + x["missing"]), -x["missing"], x["manager_name"]),
    )

    return {
        "on_time": on_time_list,
        "overtime": overtime_list,
        "missing": missing_list,
        "details": details,
        "summary": summary,
    }


def build_fill_statistics_from_records(start_date: str, end_date: str, required: int = 2) -> list[dict[str, Any]]:
    """从预约记录即时计算填报统计，避免依赖 23:30 调度生成统计表。"""
    records = get_records_by_date_range(start_date=start_date, end_date=end_date)
    dates = sorted({r["appointment_date"] for r in records if r.get("appointment_date")})
    if not dates:
        return []

    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        appt_date = record.get("appointment_date")
        manager_name = record.get("manager_name")
        if not appt_date or not manager_name:
            continue
        by_key.setdefault((appt_date, manager_name), []).append(record)

    stats: list[dict[str, Any]] = []
    for appt_date in dates:
        for manager in CUSTOMER_MANAGERS:
            manager_name = manager["name"]
            manager_records = by_key.get((appt_date, manager_name), [])
            fill_count = len(manager_records)
            fill_time = ""
            if fill_count < required:
                fill_status = "missing"
            else:
                fill_time = max(r.get("uploaded_at") or "" for r in manager_records)
                fill_status = "overtime"
                try:
                    fill_dt = datetime.fromisoformat(fill_time)
                    cutoff = datetime.combine(fill_dt.date(), datetime.strptime("19:30", "%H:%M").time())
                    fill_status = "on_time" if fill_dt <= cutoff else "overtime"
                except Exception:
                    pass
            stats.append({
                "date": appt_date,
                "manager_name": manager_name,
                "fill_status": fill_status,
                "fill_time": fill_time,
                "fill_count": fill_count,
                "reminder_count": 0,
            })
    return stats


# ====== 原有通报构建器（保留兼容） ======


def build_missing_tomorrow_booking(target_date: str, rule: dict[str, Any]) -> dict[str, Any]:
    required = int(rule.get("filter", {}).get("minimum_bookings", 2))
    records = get_records(appointment_date=target_date)
    counts = Counter(record["manager_name"] for record in records if record["manager_name"])
    items = []
    for manager in CUSTOMER_MANAGERS:
        booked = counts[manager["name"]]
        if booked < required:
            items.append({"manager_name": manager["name"], "booked": booked, "gap": required - booked})
    lines = [f"【明日预约通报】{target_date}", f"预约要求：每人至少 {required} 户。"]
    if items:
        lines.append("以下客户经理预约不足，请尽快补齐：")
        lines.extend(f"{item['manager_name']}：已预约 {item['booked']} 户，缺 {item['gap']} 户" for item in items)
    else:
        lines.append("全体客户经理均已完成明日预约要求。")
    recipients = recipients_for(rule.get("recipient_policy", {}), [item["manager_name"] for item in items])
    return {"message": "\n".join(lines), "recipients": recipients, "records": [], "items": items}


def build_tomorrow_schedule_summary(target_date: str, rule: dict[str, Any]) -> dict[str, Any]:
    records = get_records(appointment_date=target_date)
    lines = [f"【明日预约情况】{target_date}", f"共预约 {len(records)} 户。"]
    if records:
        for record in records:
            contact = record["contact_name_title"] or "未填写联系人"
            slot = record["appointment_slot"] or "时间待定"
            content = record["opportunity_content"] or record["opportunity_type"] or "未填写商机内容"
            delivery = f"，交付：{record['delivery_staff_name']}" if record["delivery_staff_name"] else ""
            lines.append(f"{record['manager_name']}｜{slot}｜{record['company_name'] or '未填写企业'}（{contact}）｜{content}{delivery}")
    else:
        lines.append("暂无明日预约记录。")
    recipients = recipients_for(rule.get("recipient_policy", {}), [])
    return {"message": "\n".join(lines), "recipients": recipients, "records": records, "items": []}


def build_visit_result_missing(target_date: str, rule: dict[str, Any]) -> dict[str, Any]:
    records = [record for record in get_records(status="missing_result") if record["appointment_date"] and record["appointment_date"] < target_date]
    lines = [f"【拜访回填通报】截至 {target_date}"]
    if records:
        lines.append("以下已预约记录尚未完整回填，请及时处理：")
        lines.extend(
            f"{record['manager_name']}｜{record['appointment_date']}｜{record['company_name'] or '未填写企业'}"
            for record in records
        )
    else:
        lines.append("暂无待回填记录。")
    recipients = recipients_for(rule.get("recipient_policy", {}), [record["manager_name"] for record in records])
    return {"message": "\n".join(lines), "recipients": recipients, "records": records, "items": []}


def build_report(target_date: str, rule: dict[str, Any]) -> dict[str, Any]:
    builders = {
        "missing_tomorrow_booking": build_missing_tomorrow_booking,
        "tomorrow_schedule_summary": build_tomorrow_schedule_summary,
        "visit_result_missing": build_visit_result_missing,
        "customer_manager_reminder": lambda td, r: build_customer_manager_reminder(td),
        "manager_brief_notice": lambda td, r: build_manager_brief_notice(td),
        "manager_detailed_notice": lambda td, r: build_manager_detailed_notice(td),
        "final_data_collection": lambda td, r: build_final_data_collection(td),
    }
    try:
        return builders[rule["template_key"]](target_date or default_target_date(), rule)
    except KeyError as exc:
        raise ValueError("未知通报模板") from exc
