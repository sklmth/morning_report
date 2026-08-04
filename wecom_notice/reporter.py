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


def next_workday(from_date: date | None = None) -> date:
    """下一个工作日（跳过周末）。

    周一~周四取次日；周五取下周一（周末不产生预约）。
    周六/周日兜底也取下周一，便于手动触发时口径一致。
    """
    base = from_date or date.today()
    weekday = base.weekday()  # 0=周一 … 6=周日
    if weekday <= 3:  # 周一~周四 → 次日
        return base + timedelta(days=1)
    return base + timedelta(days=7 - weekday)  # 周五+3 / 周六+2 / 周日+1 → 下周一


def default_target_date() -> str:
    return next_workday().isoformat()


def target_window(target_date: str) -> tuple[str, str]:
    """目标日期对应的考核窗口 (start, end)，闭区间。

    周五发的通报覆盖周六~周一三天：客户经理周末也可能有走访，
    只要这三天加起来够 2 户即算达标，所以按窗口而非单日计数。
    其余情况窗口就是目标日当天。
    """
    try:
        target = date.fromisoformat(target_date)
    except ValueError:
        return target_date, target_date
    # 目标日是周一，且今天是周五 → 窗口为周六~周一
    if target.weekday() == 0 and (target - date.today()).days > 1:
        return (target - timedelta(days=2)).isoformat(), target.isoformat()
    return target_date, target_date


def records_in_window(target_date: str, manager: str = "") -> list[dict[str, Any]]:
    """取目标窗口内的预约记录。窗口为单日时等价于按 appointment_date 精确查询。"""
    start, end = target_window(target_date)
    if start == end:
        return get_records(appointment_date=target_date, manager=manager)
    return get_records_by_date_range(start, end, manager)


def target_date_label(target_date: str = "") -> str:
    """目标日期的口语化称呼：次日为「明日」，跨周末为「周末至下周一」。"""
    if not target_date:
        return "明日"
    try:
        target = date.fromisoformat(target_date)
    except ValueError:
        return "明日"
    delta = (target - date.today()).days
    if delta == 1:
        return "明日"
    if target.weekday() == 0 and delta > 1:
        return "下周一"
    return f"{target.month}月{target.day}日"


def _is_friday_to_monday(target_date: str) -> bool:
    """今天是周五且目标日期是下周一（跨周末填报场景）。"""
    try:
        target = date.fromisoformat(target_date)
        today = date.today()
        return today.weekday() == 4 and target.weekday() == 0 and (target - today).days > 1
    except (ValueError, AttributeError):
        return False


def delivery_label(delivery_staff: str = "") -> str:
    """交付人员的展示文本，如「高装：程庆德」「未指定：无」。"""
    if not delivery_staff:
        return "未指定：无"
    if delivery_staff in [g["name"] for g in GAOZHUANG_STAFF]:
        return f"高装：{delivery_staff}"
    if delivery_staff in [z["name"] for z in ZHIYUN_ENGINEERS]:
        return f"智云：{delivery_staff}"
    return f"未指定：{delivery_staff}"


def recipients_for(policy: dict[str, Any], manager_names: list[str]) -> list[dict[str, str]]:
    target = policy.get("target", "customer_managers")
    recipients: list[dict[str, str]] = []
    if target in {"customer_managers", "customer_managers_and_management"}:
        names = set(manager_names)
        recipients.extend(person for person in CUSTOMER_MANAGERS if person["name"] in names)
    if target in {"management", "customer_managers_and_management"}:
        recipients.extend(MANAGER_RECIPIENTS)
    return recipients


# 下午茶基金规则参数。改这里即可，消息文案会跟着变。
FINE_PER_MISSING = 10      # 每次漏填的金额
FINE_PER_OVERTIME_LOT = 10 # 每满 OVERTIME_LOT_SIZE 次超时的金额
OVERTIME_LOT_SIZE = 5
ON_TIME_CUTOFF = "19:30"
MISSING_CUTOFF = "23:30"


def fine_rules_lines(overtime_count: int = 0, missing_count: int = 0) -> list[str]:
    """下午茶基金「规则警示」文案：讲清什么情况要上交，不报具体欠款金额。

    与 fine_enabled 的账单提醒分工：这里是事前警醒（规则 + 距离下次扣款还差几次），
    那边是事后账单（本月已经欠了多少钱）。所以本函数不受当月是否已欠缴影响，
    只要开关打开就会出现。
    """
    lines = [
        "",
        "--- 📋 下午茶基金规则 ---",
    ]

    # 提示离下一次扣款还有多远，比干讲规则更有警醒作用。
    # 超时和漏填各自独立成行，两项都有就都显示。
    warnings = []

    # 超时警示：根据当前次数和距离下次满档的远近，提供不同程度的提示
    lots_owed = overtime_count // OVERTIME_LOT_SIZE
    to_next_lot = OVERTIME_LOT_SIZE - (overtime_count % OVERTIME_LOT_SIZE)

    if overtime_count == 0:
        pass  # 无超时不单独提示，统一用无欠缴鼓励语
    elif to_next_lot == 1:
        # 仅剩1次缓冲，紧急提示
        warnings.append(f"⚠️ 本月已超时 {overtime_count} 次，仅剩 1 次缓冲，再超时立即扣 {FINE_PER_OVERTIME_LOT} 元。")
    elif to_next_lot == 2:
        # 还差2次，警告提示
        warnings.append(f"⚠️ 本月已超时 {overtime_count} 次，再超时 2 次就要上交 {FINE_PER_OVERTIME_LOT} 元。")
    elif to_next_lot == OVERTIME_LOT_SIZE:
        # 刚好满档（5、10、15...）
        warnings.append(f"💰 本月已超时 {overtime_count} 次（满 {lots_owed * OVERTIME_LOT_SIZE} 次），已产生 {lots_owed * FINE_PER_OVERTIME_LOT} 元。")
    elif lots_owed >= 1:
        # 满档后有缓冲（比如6、7、8、9 或 11、12...）
        warnings.append(f"💰 本月已产生 {lots_owed * FINE_PER_OVERTIME_LOT} 元，距离下次扣款还有 {to_next_lot} 次。")
    # else: 超时3~4次但不紧急时不显示，避免每天重复

    # 漏填警示：1次和多次用不同措辞
    if missing_count == 1:
        warnings.append(f"⚠️ 本月已漏填 1 次，再漏填1次需再加 {FINE_PER_MISSING} 元。")
    elif missing_count >= 2:
        warnings.append(f"⚠️ 本月已累计漏填 {missing_count} 次，每多漏1次多加 {FINE_PER_MISSING} 元。")

    # 无欠缴时随机选一句鼓励语，避免疲劳
    if not warnings:
        import random
        encouragements = [
            "✅ 本月暂无欠缴记录，今天按时填报即可继续保持！",
            "✅ 目前表现良好，请继续保持按时填报。",
            "✅ 保持当前节奏，争取本月零扣款。",
        ]
        warnings.append(random.choice(encouragements))

    lines.extend(warnings)

    # 规则说明放最后
    lines.extend([
        "",
        "💡 规则说明：",
        f"· 漏填：当天 {MISSING_CUTOFF} 前未填报 → {FINE_PER_MISSING} 元/次",
        f"· 超时：{ON_TIME_CUTOFF} 后才填报 → 每累计 {OVERTIME_LOT_SIZE} 次上交 {FINE_PER_OVERTIME_LOT} 元",
        "· 按自然月统计，次月清零重新计算",
    ])

    return lines


# ====== 新增通报构建器 ======


def build_customer_manager_reminder(target_date: str, manager_name: str, required: int = 2, notice_time: str = "") -> dict[str, Any]:
    """
    客户经理提醒消息：单独@客户经理，显示已填户数、超时/漏填历史、今日提醒次数。
    填了2户及以上的不返回消息（should_send=False）。
    实习期人员（exclude_reminder=True）不发送提醒。
    """
    # 检查是否需要排除提醒
    manager_obj = next((m for m in CUSTOMER_MANAGERS if m["name"] == manager_name), None)
    if manager_obj and manager_obj.get("exclude_reminder", False):
        return {"message": "", "recipients": [], "should_send": False, "manager_name": manager_name, "excluded": True}

    records = records_in_window(target_date, manager_name)
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

    # 日期行 / 标题：周五跨周末场景单独标注「下周一」
    if _is_friday_to_monday(target_date):
        date_line = f"📅 目标日期：{target_date}（下周一）"
        title_label = "周五预约填报"
    else:
        date_line = f"📅 日期：{target_date}"
        title_label = f"{target_date_label(target_date)}预约填报"

    # 通报时间：优先使用调用方传入的本轮触发时间，保证同一轮所有经理显示同一时刻
    current_time = notice_time if notice_time else datetime.now().strftime("%H:%M")
    lines = [
        f"{emoji} @{manager_name}",
        "",
        f"{title_label}（今天第{reminder_seq}次提醒）",
        f"⏰ 通报时间：{current_time}",
        date_line,
        f"✅ 已填：{current_count} 户",
        f"⚠️ 还需：{gap} 户",
    ]

    # 判断当前时间是否超过准时截止线（19:30）
    now = datetime.now()
    cutoff_time = datetime.combine(now.date(), datetime.strptime(ON_TIME_CUTOFF, "%H:%M").time())
    is_overtime_period = now > cutoff_time

    if is_overtime_period:
        # 19:30后：已超时，提示仍需完成避免漏填
        lines.extend([
            "",
            f"⏱️ 当前已超过准时时间（{ON_TIME_CUTOFF}）",
            f"本次填报将记为超时，但仍需完成以避免漏填",
            f"⚠️ 请在 {MISSING_CUTOFF} 前完成，否则记为漏填（{FINE_PER_MISSING}元/次）",
        ])
    else:
        # 19:30前：还能准时，显示剩余时间
        remaining_minutes = int((cutoff_time - now).total_seconds() / 60)
        if remaining_minutes > 0:
            lines.extend([
                "",
                f"💡 距离准时截止（{ON_TIME_CUTOFF}）还有 {remaining_minutes} 分钟",
                "现在填报可避免超时记录",
            ])
        else:
            # 边界情况：时间刚好或负数（理论上不会走到这里）
            lines.extend([
                "",
                f"💡 准时截止时间为 {ON_TIME_CUTOFF}",
                "请尽快完成填报",
            ])

    lines.append("")

    if overtime_count > 0 or missing_count > 0:
        lines.append("")
        lines.append("📊 本月记录：")
        if overtime_count > 0:
            lines.append(f"   ⏱️ 超时填报：{overtime_count} 次")
        if missing_count > 0:
            lines.append(f"   ❌ 漏填：{missing_count} 次")

    # 已产生欠缴的账单（fine_enabled）：算钱，只在真的欠了才显示
    from wecom_notice.db import get_setting
    if get_setting("fine_enabled", "false") == "true":
        fine_from_missing = missing_count * 10          # 每次漏填 10元
        fine_from_overtime = (overtime_count // 5) * 10 # 每累计5次超时 10元
        total_fine = fine_from_missing + fine_from_overtime
        if total_fine > 0:
            lines.append("")
            lines.append("☕ 下午茶基金提醒：")
            if missing_count >= 1:
                lines.append(f"   · 本月漏填 {missing_count} 次（× 10 元/次）= {fine_from_missing} 元")
            if overtime_count >= 5:
                lines.append(f"   · 本月超时填报 {overtime_count} 次（每5次 10 元）= {fine_from_overtime} 元")
            lines.append(f"   请上交 {total_fine} 元至部门下午茶基金。")

    lines.extend([
        "",
        f"💡 温馨提示：请尽快完成填报，确保{target_date_label(target_date)}工作顺利开展~"
    ])

    # 规则警示（fine_rules_enabled）：不算钱，只讲清什么情况要上交，起警醒作用。
    # 与上面的账单提醒相互独立，可单开、可同开。
    if get_setting("fine_rules_enabled", "false") == "true":
        lines.extend(fine_rules_lines(overtime_count, missing_count))

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
    records = records_in_window(target_date)
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
        f"🚨【预约填报督办】{target_date}",
        f"⏰ 当前时间：{current_time}",
        f"截至目前，仍有 {len(not_filled)} 名客户经理未完成今日预约填报，请知悉！",
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


def _top3_with_ties(data: dict[str, int]) -> list[tuple[str, int]]:
    """
    取前三名，并列时继续列出。
    例如：第3名有2人并列18次，则返回4条记录。
    """
    if not data:
        return []

    sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_data) <= 3:
        return sorted_data

    # 找到第3名的次数
    third_count = sorted_data[2][1]
    result = sorted_data[:3]

    # 继续添加与第3名并列的
    for item in sorted_data[3:]:
        if item[1] == third_count:
            result.append(item)
        else:
            break

    return result


def build_manager_detailed_notice(target_date: str, required: int = 2) -> dict[str, Any]:
    """
    第二个通报（详细版）：包含今日情况和累计情况。
    - 今日情况：没填的在前面，填了的显示拜访客户和预约交付人员
    - 累计情况：漏填、超时、准时，做得好的在前面，加emoji
    实习期人员（exclude_reminder=True）不计入统计。
    """
    records = records_in_window(target_date)
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
                details.append(f"    · {company}（{delivery_label(r['delivery_staff_name'])}）")
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
    detail_title = f"【周五预约填报通报】{target_date}（下周一）" if _is_friday_to_monday(target_date) else f"【{target_date_label(target_date)}预约详细通报】{target_date}"
    lines = [
        detail_title,
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

    # 准时填报（做得好的）TOP3
    medals = ["🥇", "🥈", "🥉", "🏅"]
    if on_time_managers:
        top3_on_time = _top3_with_ties(on_time_managers)
        lines.append("")
        lines.append("👍 准时填报（19:30前完成）TOP3：")
        for idx, (mgr, cnt) in enumerate(top3_on_time):
            medal = medals[min(idx, 3)]
            lines.append(f"   {medal} {mgr}：{cnt} 次")

    # 超时填报 TOP3
    if overtime_managers:
        top3_overtime = _top3_with_ties(overtime_managers)
        lines.append("")
        lines.append("⏱️ 超时填报（19:30-23:30）TOP3：")
        for mgr, cnt in top3_overtime:
            lines.append(f"   {mgr}：{cnt} 次")

    # 漏填情况 TOP3
    if missing_managers:
        top3_missing = _top3_with_ties(missing_managers)
        lines.append("")
        lines.append("❌ 漏填情况（23:30未完成）TOP3：")
        for mgr, cnt in top3_missing:
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

    records = records_in_window(target_date)
    counts = Counter(record["manager_name"] for record in records if record["manager_name"])

    # 获取今日所有提醒日志，判断最后一次填报完成的时间
    today_str = date.today().isoformat()
    # 2026-08-04 为系统启用基线日，全天按准时处理；从 08-05 开始正常计入。
    baseline_day = today_str == "2026-08-04"

    results = []
    for manager in CUSTOMER_MANAGERS:
        # 跳过实习期人员
        if manager.get("exclude_reminder", False):
            continue

        count = counts[manager["name"]]
        mgr_name = manager["name"]

        if baseline_day:
            upsert_fill_statistics(today_str, mgr_name, "on_time", "", count)
            results.append({"manager": mgr_name, "status": "on_time", "count": count})
        elif count < required:
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


def build_weekly_report() -> dict[str, Any]:
    """
    周通报：本月预约填报情况汇总（准时/超时/漏填各取前三），附下午茶基金清单。
    发送对象：全体客户经理 + 管理者。
    计划：周三 12:15 / 周日 12:00 各发一次。
    """
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    end_date = today.isoformat()

    all_stats = get_fill_statistics(start_date=month_start, end_date=end_date)
    if not all_stats:
        all_stats = build_fill_statistics_from_records(month_start, end_date)

    # 初始化每位参与统计的客户经理
    manager_stats: dict[str, dict[str, int]] = {}
    for m in CUSTOMER_MANAGERS:
        if m.get("exclude_reminder", False):
            continue
        manager_stats[m["name"]] = {"on_time": 0, "overtime": 0, "missing": 0}

    for stat in all_stats:
        mgr = stat["manager_name"]
        status = stat["fill_status"]
        if mgr in manager_stats and status in manager_stats[mgr]:
            manager_stats[mgr][status] += 1

    on_time_top3 = _top3_with_ties({m: s["on_time"] for m, s in manager_stats.items()})
    overtime_top3 = _top3_with_ties({m: s["overtime"] for m, s in manager_stats.items()})
    missing_top3 = _top3_with_ties({m: s["missing"] for m, s in manager_stats.items()})

    # 罚款计算（按金额倒序）
    fines = []
    for mgr, s in manager_stats.items():
        fine_missing = s["missing"] * 10
        fine_overtime = (s["overtime"] // 5) * 10
        total = fine_missing + fine_overtime
        if total > 0:
            fines.append({
                "name": mgr,
                "missing": s["missing"],
                "overtime": s["overtime"],
                "fine_missing": fine_missing,
                "fine_overtime": fine_overtime,
                "total": total,
            })
    fines.sort(key=lambda x: x["total"], reverse=True)

    # 构建消息
    now_dt = datetime.now()
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now_dt.weekday()]
    month_label = f"{today.year}年{today.month}月"

    lines = [
        f"📊【本月预约填报周报】{month_label}",
        f"📅 统计周期：{month_start[5:]} ~ {end_date[5:]} | 数据截至 {weekday_cn} {now_dt.strftime('%H:%M')}",
        "",
        "━━━━━━ 📈 本月填报情况 ━━━━━━",
        "",
        "👍 准时填报（19:30前完成）TOP3：",
    ]
    medals = ["🥇", "🥈", "🥉", "🏅"]
    if on_time_top3:
        for idx, (name, cnt) in enumerate(on_time_top3):
            medal = medals[min(idx, 3)]
            lines.append(f"   {medal} {name}：{cnt} 次")
    else:
        lines.append("   暂无准时填报记录")

    lines.extend(["", "⏱️ 超时填报（19:30-23:30）TOP3："])
    if overtime_top3:
        for name, cnt in overtime_top3:
            lines.append(f"   {name}：{cnt} 次")
    else:
        lines.append("   暂无超时记录")

    lines.extend(["", "❌ 漏填情况（23:30未完成）TOP3："])
    if missing_top3:
        for name, cnt in missing_top3:
            lines.append(f"   {name}：{cnt} 次")
    else:
        lines.append("   暂无漏填记录 🎉")

    lines.extend(["", "━━━━━━ ☕ 下午茶基金 ━━━━━━", ""])
    if fines:
        for f in fines:
            icon = "💸" if f["total"] >= 40 else ("⚠️" if f["total"] >= 20 else "📌")
            parts = []
            if f["missing"] >= 1:
                parts.append(f"漏填 {f['missing']} 次")
            if f["overtime"] >= 5:
                parts.append(f"超时 {f['overtime']} 次（每5次10元）")
            lines.append(f"   {icon} {f['name']}   {' + '.join(parts)} = {f['total']} 元")
    else:
        lines.append("   ✅ 本月暂无应缴记录，继续保持！")

    # 周报 @ 全员：11 名客户经理（实习期除外）+ 3 位管理者，共 14 人。
    recipients = [m for m in CUSTOMER_MANAGERS if not m.get("exclude_reminder", False)] + MANAGER_RECIPIENTS

    return {
        "message": "\n".join(lines),
        "recipients": recipients,
        "should_send": True,
    }


def build_biweekly_report() -> dict[str, Any]:
    """
    半月报：本月1-15号预约填报情况汇总（准时/超时/漏填各取前三，并列时续列），附下午茶基金清单。
    发送对象：全体客户经理 + 管理者。
    计划：每月15号 12:00 发送。
    """
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    end_date = today.replace(day=15).isoformat()  # 固定到15号

    all_stats = get_fill_statistics(start_date=month_start, end_date=end_date)
    if not all_stats:
        all_stats = build_fill_statistics_from_records(month_start, end_date)

    # 初始化每位参与统计的客户经理
    manager_stats: dict[str, dict[str, int]] = {}
    for m in CUSTOMER_MANAGERS:
        if m.get("exclude_reminder", False):
            continue
        manager_stats[m["name"]] = {"on_time": 0, "overtime": 0, "missing": 0}

    for stat in all_stats:
        mgr = stat["manager_name"]
        status = stat["fill_status"]
        if mgr in manager_stats and status in manager_stats[mgr]:
            manager_stats[mgr][status] += 1

    on_time_top3 = _top3_with_ties({m: s["on_time"] for m, s in manager_stats.items()})
    overtime_top3 = _top3_with_ties({m: s["overtime"] for m, s in manager_stats.items()})
    missing_top3 = _top3_with_ties({m: s["missing"] for m, s in manager_stats.items()})

    # 罚款计算
    fines = []
    for mgr, s in manager_stats.items():
        fine_missing = s["missing"] * 10
        fine_overtime = (s["overtime"] // 5) * 10
        total = fine_missing + fine_overtime
        if total > 0:
            fines.append({
                "name": mgr,
                "missing": s["missing"],
                "overtime": s["overtime"],
                "fine_missing": fine_missing,
                "fine_overtime": fine_overtime,
                "total": total,
            })
    fines.sort(key=lambda x: x["total"], reverse=True)

    # 构建消息
    now_dt = datetime.now()
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now_dt.weekday()]
    month_label = f"{today.year}年{today.month}月"

    lines = [
        f"📊【本月预约填报半月报】{month_label}",
        f"📅 统计周期：{month_start[5:]} ~ {end_date[5:]} | 数据截至 {weekday_cn} {now_dt.strftime('%H:%M')}",
        "",
        "━━━━━━ 📈 本月填报情况 ━━━━━━",
        "",
        "👍 准时填报（19:30前完成）TOP3：",
    ]
    medals = ["🥇", "🥈", "🥉", "🏅"]
    if on_time_top3:
        for idx, (name, cnt) in enumerate(on_time_top3):
            medal = medals[min(idx, 3)]
            lines.append(f"   {medal} {name}：{cnt} 次")
    else:
        lines.append("   暂无准时填报记录")

    lines.extend(["", "⏱️ 超时填报（19:30-23:30）TOP3："])
    if overtime_top3:
        for name, cnt in overtime_top3:
            lines.append(f"   {name}：{cnt} 次")
    else:
        lines.append("   暂无超时记录")

    lines.extend(["", "❌ 漏填情况（23:30未完成）TOP3："])
    if missing_top3:
        for name, cnt in missing_top3:
            lines.append(f"   {name}：{cnt} 次")
    else:
        lines.append("   暂无漏填记录 🎉")

    lines.extend(["", "━━━━━━ ☕ 下午茶基金 ━━━━━━", ""])
    if fines:
        for f in fines:
            icon = "💸" if f["total"] >= 40 else ("⚠️" if f["total"] >= 20 else "📌")
            parts = []
            if f["missing"] >= 1:
                parts.append(f"漏填 {f['missing']} 次")
            if f["overtime"] >= 5:
                parts.append(f"超时 {f['overtime']} 次（每5次10元）")
            lines.append(f"   {icon} {f['name']}   {' + '.join(parts)} = {f['total']} 元")
    else:
        lines.append("   ✅ 本月暂无应缴记录，继续保持！")

    return {
        "message": "\n".join(lines),
        "recipients": [],
        "mention_all": True,
        "should_send": True,
    }


def build_monthly_report() -> dict[str, Any]:
    """
    月报：本月全月预约填报情况汇总（准时/超时/漏填各取前三，并列时续列），附下午茶基金清单。
    发送对象：@all 所有人（客户经理 + 管理者 + 其他）。
    计划：每月最后一天 12:00 发送。
    """
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    # 月末：下个月1号的前一天
    next_month = today.replace(day=28) + timedelta(days=4)
    month_end = (next_month.replace(day=1) - timedelta(days=1)).isoformat()
    end_date = today.isoformat()  # 实际截至今天

    all_stats = get_fill_statistics(start_date=month_start, end_date=end_date)
    if not all_stats:
        all_stats = build_fill_statistics_from_records(month_start, end_date)

    # 初始化每位参与统计的客户经理
    manager_stats: dict[str, dict[str, int]] = {}
    for m in CUSTOMER_MANAGERS:
        if m.get("exclude_reminder", False):
            continue
        manager_stats[m["name"]] = {"on_time": 0, "overtime": 0, "missing": 0}

    for stat in all_stats:
        mgr = stat["manager_name"]
        status = stat["fill_status"]
        if mgr in manager_stats and status in manager_stats[mgr]:
            manager_stats[mgr][status] += 1

    on_time_top3 = _top3_with_ties({m: s["on_time"] for m, s in manager_stats.items()})
    overtime_top3 = _top3_with_ties({m: s["overtime"] for m, s in manager_stats.items()})
    missing_top3 = _top3_with_ties({m: s["missing"] for m, s in manager_stats.items()})

    # 罚款计算
    fines = []
    for mgr, s in manager_stats.items():
        fine_missing = s["missing"] * 10
        fine_overtime = (s["overtime"] // 5) * 10
        total = fine_missing + fine_overtime
        if total > 0:
            fines.append({
                "name": mgr,
                "missing": s["missing"],
                "overtime": s["overtime"],
                "fine_missing": fine_missing,
                "fine_overtime": fine_overtime,
                "total": total,
            })
    fines.sort(key=lambda x: x["total"], reverse=True)

    # 构建消息
    now_dt = datetime.now()
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now_dt.weekday()]
    month_label = f"{today.year}年{today.month}月"

    lines = [
        f"📊【本月预约填报月报】{month_label}",
        f"📅 统计周期：{month_start[5:]} ~ {end_date[5:]} | 数据截至 {weekday_cn} {now_dt.strftime('%H:%M')}",
        "",
        "━━━━━━ 📈 本月填报情况 ━━━━━━",
        "",
        "👍 准时填报（19:30前完成）TOP3：",
    ]
    medals = ["🥇", "🥈", "🥉", "🏅"]
    if on_time_top3:
        for idx, (name, cnt) in enumerate(on_time_top3):
            medal = medals[min(idx, 3)]
            lines.append(f"   {medal} {name}：{cnt} 次")
    else:
        lines.append("   暂无准时填报记录")

    lines.extend(["", "⏱️ 超时填报（19:30-23:30）TOP3："])
    if overtime_top3:
        for name, cnt in overtime_top3:
            lines.append(f"   {name}：{cnt} 次")
    else:
        lines.append("   暂无超时记录")

    lines.extend(["", "❌ 漏填情况（23:30未完成）TOP3："])
    if missing_top3:
        for name, cnt in missing_top3:
            lines.append(f"   {name}：{cnt} 次")
    else:
        lines.append("   暂无漏填记录 🎉")

    lines.extend(["", "━━━━━━ ☕ 下午茶基金 ━━━━━━", ""])
    if fines:
        for f in fines:
            icon = "💸" if f["total"] >= 40 else ("⚠️" if f["total"] >= 20 else "📌")
            parts = []
            if f["missing"] >= 1:
                parts.append(f"漏填 {f['missing']} 次")
            if f["overtime"] >= 5:
                parts.append(f"超时 {f['overtime']} 次（每5次10元）")
            lines.append(f"   {icon} {f['name']}   {' + '.join(parts)} = {f['total']} 元")
    else:
        lines.append("   ✅ 本月暂无应缴记录，继续保持！")

    # 月报 @all：传递空 recipients，由 sender 特殊处理为 @all
    return {
        "message": "\n".join(lines),
        "recipients": [],  # 空列表表示 @all
        "should_send": True,
        "mention_all": True,  # 标记需要 @all
    }


# ====== 原有通报构建器（保留兼容） ======


def build_missing_tomorrow_booking(target_date: str, rule: dict[str, Any]) -> dict[str, Any]:
    """明日预约不足通报 - 参考简洁通报风格"""
    required = int(rule.get("filter", {}).get("minimum_bookings", 2))
    records = records_in_window(target_date)
    counts = Counter(record["manager_name"] for record in records if record["manager_name"])

    not_filled = []
    filled = []

    for manager in CUSTOMER_MANAGERS:
        # 跳过实习期人员
        if manager.get("exclude_reminder", False):
            continue

        booked = counts[manager["name"]]
        if booked < required:
            not_filled.append({"name": manager["name"], "booked": booked, "gap": required - booked})
        else:
            filled.append({"name": manager["name"], "booked": booked})

    if not not_filled:
        # 全部达标，返回空消息
        return {"message": "", "recipients": [], "records": [], "items": [], "should_send": False}

    current_time = datetime.now().strftime("%H:%M")
    lines = [
        f"🚨【预约填报督办】{target_date}",
        f"⏰ 当前时间：{current_time}",
        f"截至目前，仍有 {len(not_filled)} 名客户经理未完成今日预约填报，请知悉！",
        "",
        "⚠️ 未完成填报：",
    ]

    for item in not_filled:
        lines.append(f"❌ {item['name']}：已填报 {item['booked']} 户，还差 {item['gap']} 户")

    if filled:
        lines.extend(["", "✅ 已完成填报："])
        for item in filled:
            lines.append(f"✅ {item['name']}：已填报 {item['booked']} 户")

    recipients = recipients_for(rule.get("recipient_policy", {}), [item["name"] for item in not_filled])
    return {"message": "\n".join(lines), "recipients": recipients, "records": [], "items": not_filled, "should_send": True}


def build_tomorrow_schedule_summary(target_date: str, rule: dict[str, Any]) -> dict[str, Any]:
    """明日预约汇总 - 与详细通报同一格式：未完成在前，已完成只列企业和交付人员。

    每人最多列 3 条，超出折叠为「... 还有 N 户」。时段、联系人、商机内容不再展示，
    避免 20 户以上时消息过长。
    """
    required = int(rule.get("filter", {}).get("minimum_bookings", 2))
    records = records_in_window(target_date)
    counts = Counter(record["manager_name"] for record in records if record["manager_name"])
    current_time = datetime.now().strftime("%H:%M")

    not_filled = []
    filled = []

    for manager in CUSTOMER_MANAGERS:
        # 跳过实习期人员
        if manager.get("exclude_reminder", False):
            continue

        count = counts[manager["name"]]
        if count < required:
            not_filled.append(f"❌ {manager['name']}：已填报 {count} 户，还差 {required - count} 户")
            continue

        mgr_recs = [r for r in records if r["manager_name"] == manager["name"]]
        filled.append(f"✅ {manager['name']}：{count} 户")
        for record in mgr_recs[:3]:
            company = record["company_name"] or "未填写企业"
            filled.append(f"    · {company}（{delivery_label(record['delivery_staff_name'])}）")
        if len(mgr_recs) > 3:
            filled.append(f"    ... 还有 {len(mgr_recs) - 3} 户")

    lines = [
        f"【周五预约填报情况】{target_date}（下周一）" if _is_friday_to_monday(target_date) else f"【{target_date_label(target_date)}预约情况】{target_date}",
        f"⏰ 通报时间：{current_time}",
        "",
        f"共预约 {len(records)} 户。",
    ]

    if not_filled:
        lines.extend(["", "⚠️ 未完成填报：", *not_filled])
    if filled:
        lines.extend(["", "✅ 已完成填报：", *filled])

    recipients = recipients_for(rule.get("recipient_policy", {}), [])
    return {"message": "\n".join(lines), "recipients": recipients, "records": records, "items": []}


def build_visit_result_missing(target_date: str, rule: dict[str, Any]) -> dict[str, Any]:
    """拜访回填提醒 - 按客户经理分组显示待回填记录"""
    records = [record for record in get_records(status="missing_result") if record["appointment_date"] and record["appointment_date"] < target_date]

    current_time = datetime.now().strftime("%H:%M")
    lines = [
        f"【拜访回填提醒】截至 {target_date}",
        f"⏰ 通报时间：{current_time}",
        "",
    ]

    if records:
        lines.append(f"以下 {len(records)} 条已预约记录尚未完整回填，请及时处理：")
        lines.append("")

        # 按客户经理分组
        manager_records = {}
        for record in records:
            mgr = record["manager_name"]
            if mgr not in manager_records:
                manager_records[mgr] = []
            manager_records[mgr].append(record)

        # 按客户经理名称排序输出
        for manager_name in sorted(manager_records.keys()):
            mgr_recs = manager_records[manager_name]
            lines.append(f"❌ {manager_name}：{len(mgr_recs)} 条")
            for record in mgr_recs:
                appt_date = record["appointment_date"]
                company = record["company_name"] or "未填写企业"
                contact = record["contact_name_title"] or ""

                if contact:
                    lines.append(f"    · {appt_date}｜{company}（{contact}）")
                else:
                    lines.append(f"    · {appt_date}｜{company}")
    else:
        lines.append("✅ 暂无待回填记录，工作进展顺利！")

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
