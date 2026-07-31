import hashlib
import json
from datetime import date, datetime
from typing import Any

FIELD_MAP = {
    "客户经理姓名": "manager_name",
    "拜访对象类型": "object_type",
    "企业名称": "company_name",
    "拜访对象姓名+职位": "contact_name_title",
    "拜访对象手机号": "contact_mobile",
    "预约上门日期": "appointment_date",
    "预约时间段": "appointment_slot",
    "是否需要集中派单": "need_dispatch",
    "预约交付人员姓名": "delivery_staff_name",
    "商机类型": "opportunity_type",
    "商机类型:补充填空": "opportunity_type_extra",
    "商机内容（上门计划）": "opportunity_content",
    "智慧座舱图是否已发群": "cockpit_sent",
    "豆包BEIK图是否已发群": "doubao_beik_sent",
    "拜访结果（上门后回填）": "visit_result",
    "实际上门拜访日期": "actual_visit_date",
    "实际情况上门拜访日期": "actual_visit_date",
    "拜访情况": "visit_situation",
    "商机转化情况": "conversion_status",
    "商机积分": "opportunity_points",
    "折合高套数量": "gaotao_count",
    "计划受理时间": "planned_accept_time",
    "改约时间": "reschedule_time",
    "改约原因/无法上门原因": "reschedule_reason",
}
EXCLUDED_UPLOAD_FIELDS = {"拜访照片", *(f"拜访图片_{index}" for index in range(1, 6))}


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(text(item) for item in value if text(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def date_text(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()[:10]
    return text(value).replace("/", "-")[:10]


def number(value: Any) -> float:
    raw = text(value).replace(",", "")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def normalize_record(item: dict[str, Any]) -> dict[str, Any]:
    raw_fields = item.get("fields") if isinstance(item.get("fields"), dict) else item
    fields = {key: value for key, value in raw_fields.items() if key not in EXCLUDED_UPLOAD_FIELDS}
    normalized = {column: "" for column in FIELD_MAP.values()}
    for source, target in FIELD_MAP.items():
        value = fields.get(source, "")
        normalized[target] = date_text(value) if target.endswith("_date") or target.endswith("_time") else text(value)

    normalized["images_json"] = "{}"
    normalized["opportunity_points"] = number(fields.get("商机积分", ""))
    normalized["gaotao_count"] = number(fields.get("折合高套数量", ""))
    source_record_id = text(item.get("record_id") or item.get("id"))
    normalized["source_record_id"] = source_record_id or None
    normalized["raw_json"] = json.dumps(fields, ensure_ascii=False, sort_keys=True, default=str)
    normalized["payload_hash"] = hashlib.sha256(normalized["raw_json"].encode("utf-8")).hexdigest()
    return normalized
