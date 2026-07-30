from wecom_notice.db import get_rule
from wecom_notice.reporter import build_report


def run_rule_once(rule_key: str, target_date: str = ""):
    rule = get_rule(rule_key)
    if not rule:
        raise ValueError("规则不存在")
    return build_report(target_date, rule)
