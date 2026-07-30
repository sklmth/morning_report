from collections import Counter
from datetime import date, timedelta
from typing import Any

from wecom_notice.config import CUSTOMER_MANAGERS, MANAGER_RECIPIENTS
from wecom_notice.db import get_records


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
    }
    try:
        return builders[rule["template_key"]](target_date or default_target_date(), rule)
    except KeyError as exc:
        raise ValueError("未知通报模板") from exc
