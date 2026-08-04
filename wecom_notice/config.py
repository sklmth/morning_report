import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT_DIR / "runtime"
DB_PATH = Path(os.environ.get("WECOM_NOTICE_DB_PATH", RUNTIME_DIR / "wecom_notice.db"))
# 端州政企群机器人 webhook。默认值即正式群，可用环境变量 WECOM_NOTICE_WEBHOOK_URL 覆盖。
DEFAULT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=866c5319-0f4a-42fe-8465-f4b3de554c61"
WEBHOOK_URL = os.environ.get("WECOM_NOTICE_WEBHOOK_URL", DEFAULT_WEBHOOK_URL)
KINGSOFT_WEBHOOK_URL = "https://www.kdocs.cn/chatflow/api/v2/func/webhook/3HO9aSGTCOI0baONAtcctbiSu77"

# Excel 中当前出现的客户经理名单。补充手机号或企业微信 userid 后即可支持群内 @。
CUSTOMER_MANAGERS = [
    {"name": "麦海芬", "team": "党政军团队", "mobile": "13360254388", "wecom_userid": "", "role": "customer_manager"},
    {"name": "黄淡妮", "team": "党政军团队", "mobile": "18902365779", "wecom_userid": "", "role": "customer_manager"},
    {"name": "邱海燕", "team": "党政军团队", "mobile": "18933133113", "wecom_userid": "", "role": "customer_manager"},
    {"name": "李东", "team": "党政军团队", "mobile": "18929819998", "wecom_userid": "", "role": "customer_manager"},
    {"name": "王锦添", "team": "党政军团队", "mobile": "18126555505", "wecom_userid": "", "role": "customer_manager"},
    {"name": "黄观霞", "team": "党政军团队", "mobile": "18929840777", "wecom_userid": "", "role": "customer_manager"},
    {"name": "谢卓和", "team": "大企业团队", "mobile": "13376562252", "wecom_userid": "", "role": "customer_manager"},
    {"name": "伍颖敏", "team": "大企业团队", "mobile": "13376562181", "wecom_userid": "", "role": "customer_manager"},
    {"name": "邓天群", "team": "大企业团队", "mobile": "18938310028", "wecom_userid": "", "role": "customer_manager", "exclude_reminder": True},  # 实习期暂不提醒
    {"name": "李玉强", "team": "大企业团队", "mobile": "13376562080", "wecom_userid": "", "role": "customer_manager"},
    {"name": "张小敏", "team": "大企业团队", "mobile": "18933134919", "wecom_userid": "", "role": "customer_manager"},
    {"name": "具进康", "team": "大企业团队", "mobile": "13822605579", "wecom_userid": "", "role": "customer_manager"},
]

# 高端装维人员（用于"预约交付人员姓名"字段选择）
GAOZHUANG_STAFF = [
    {"name": "程庆德", "mobile": "", "wecom_userid": "", "role": "gaozhuang"},
    {"name": "刘奇峻", "mobile": "", "wecom_userid": "", "role": "gaozhuang"},
    {"name": "龙家宝", "mobile": "", "wecom_userid": "", "role": "gaozhuang"},
    {"name": "罗紫杰", "mobile": "", "wecom_userid": "", "role": "gaozhuang"},
    {"name": "莫健铭", "mobile": "", "wecom_userid": "", "role": "gaozhuang"},
    {"name": "吴广仁", "mobile": "", "wecom_userid": "", "role": "gaozhuang"},
    {"name": "王洪明", "mobile": "", "wecom_userid": "", "role": "gaozhuang"},
    {"name": "陈梓铭", "mobile": "", "wecom_userid": "", "role": "gaozhuang"},
]

# 智云工程师（用于"预约交付人员姓名"字段选择）
ZHIYUN_ENGINEERS = [
    {"name": "零樑", "mobile": "", "wecom_userid": "", "role": "zhiyun"},
    {"name": "何而恒", "mobile": "", "wecom_userid": "", "role": "zhiyun"},
    {"name": "魏垚晖", "mobile": "", "wecom_userid": "", "role": "zhiyun"},
    {"name": "吴文懿", "mobile": "", "wecom_userid": "", "role": "zhiyun"},
    {"name": "莫尧桂", "mobile": "", "wecom_userid": "", "role": "zhiyun"},
    {"name": "郭剑鸿", "mobile": "", "wecom_userid": "", "role": "zhiyun"},
    {"name": "梁钧鹏", "mobile": "", "wecom_userid": "", "role": "zhiyun"},
]

# 管理者名单（经理和副经理）
MANAGER_RECIPIENTS = [
    {"name": "钟俊杰", "mobile": "18929809369", "wecom_userid": "", "role": "manager", "title": "正经理"},
    {"name": "张端", "mobile": "13376568281", "wecom_userid": "", "role": "deputy_manager", "title": "副经理"},
    {"name": "梁天霖", "mobile": "18933131302", "wecom_userid": "", "role": "deputy_manager", "title": "副经理"},
]

DEFAULT_RULES = [
    {
        "key": "missing_tomorrow_booking",
        "name": "明日预约不足两户通报",
        "enabled": False,
        "trigger_type": "manual",
        "cron_expr": "",
        "filter": {"minimum_bookings": 2},
        "recipient_policy": {"target": "customer_managers_and_management"},
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
