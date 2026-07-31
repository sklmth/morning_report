import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT_DIR / "runtime"
DB_PATH = Path(os.environ.get("WECOM_NOTICE_DB_PATH", RUNTIME_DIR / "wecom_notice.db"))
WEBHOOK_URL = os.environ.get("WECOM_NOTICE_WEBHOOK_URL", "")

# Excel 中当前出现的客户经理名单。补充手机号或企业微信 userid 后即可支持群内 @。
CUSTOMER_MANAGERS = [
    {"name": "麦海芬", "team": "党政军团队", "mobile": "", "wecom_userid": "", "role": "customer_manager"},
    {"name": "黄淡妮", "team": "党政军团队", "mobile": "", "wecom_userid": "", "role": "customer_manager"},
    {"name": "邱海燕", "team": "党政军团队", "mobile": "", "wecom_userid": "", "role": "customer_manager"},
    {"name": "李东", "team": "党政军团队", "mobile": "", "wecom_userid": "", "role": "customer_manager"},
    {"name": "王锦添", "team": "党政军团队", "mobile": "", "wecom_userid": "", "role": "customer_manager"},
    {"name": "黄观霞", "team": "党政军团队", "mobile": "", "wecom_userid": "", "role": "customer_manager"},
    {"name": "谢卓和", "team": "大企业团队", "mobile": "", "wecom_userid": "", "role": "customer_manager"},
    {"name": "伍颖敏", "team": "大企业团队", "mobile": "", "wecom_userid": "", "role": "customer_manager"},
    {"name": "邓天群", "team": "大企业团队", "mobile": "", "wecom_userid": "", "role": "customer_manager"},
    {"name": "李玉强", "team": "大企业团队", "mobile": "", "wecom_userid": "", "role": "customer_manager"},
    {"name": "张小敏", "team": "大企业团队", "mobile": "", "wecom_userid": "", "role": "customer_manager"},
    {"name": "具进康", "team": "大企业团队", "mobile": "", "wecom_userid": "", "role": "customer_manager"},
]

# 填入实际姓名、手机号或企业微信 userid 后，明日预约汇总会自动 @ 这些管理人员。
MANAGER_RECIPIENTS = [
    {"name": "经理一", "mobile": "", "wecom_userid": "", "role": "manager"},
    {"name": "经理二", "mobile": "", "wecom_userid": "", "role": "manager"},
    {"name": "副经理", "mobile": "", "wecom_userid": "", "role": "deputy_manager"},
]

DEFAULT_RULES = [
    {
        "key": "missing_tomorrow_booking",
        "name": "明日预约不足两户通报",
        "enabled": False,
        "trigger_type": "manual",
        "cron_expr": "",
        "filter": {"minimum_bookings": 2},
        "recipient_policy": {"target": "customer_managers"},
        "template_key": "missing_tomorrow_booking",
    },
    {
        "key": "tomorrow_schedule_summary",
        "name": "明日预约情况汇总",
        "enabled": False,
        "trigger_type": "manual",
        "cron_expr": "",
        "filter": {},
        "recipient_policy": {"target": "management"},
        "template_key": "tomorrow_schedule_summary",
    },
    {
        "key": "visit_result_missing",
        "name": "已预约未回填通报",
        "enabled": False,
        "trigger_type": "manual",
        "cron_expr": "",
        "filter": {},
        "recipient_policy": {"target": "customer_managers_and_management"},
        "template_key": "visit_result_missing",
    },
]
