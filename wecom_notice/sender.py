import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from wecom_notice.config import WEBHOOK_URL


def send_text(message: str, recipients: list[dict[str, str]]) -> dict:
    if not WEBHOOK_URL:
        raise RuntimeError("未配置 WECOM_NOTICE_WEBHOOK_URL")
    webhook_url = WEBHOOK_URL

    userids = [person["wecom_userid"] for person in recipients if person.get("wecom_userid")]
    mobiles = [person["mobile"] for person in recipients if person.get("mobile") and not person.get("wecom_userid")]
    payload = {
        "msgtype": "text",
        "text": {
            "content": message,
            "mentioned_list": userids,
            "mentioned_mobile_list": mobiles,
        },
    }
    request = Request(
        webhook_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(f"企业微信请求失败: HTTP {exc.code} {exc.read().decode('utf-8', 'replace')}") from exc
    except URLError as exc:
        raise RuntimeError(f"企业微信网络请求失败: {exc.reason}") from exc
    result = json.loads(body)
    if result.get("errcode") != 0:
        raise RuntimeError(f"企业微信返回错误: {body}")
    return result
