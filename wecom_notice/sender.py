import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from wecom_notice.config import WEBHOOK_URL


def _send_webhook(payload: dict) -> dict:
    """
    通用 Webhook 发送函数

    Args:
        payload: 消息 payload（包含 msgtype 和对应字段）

    Returns:
        企业微信 API 响应
    """
    if not WEBHOOK_URL:
        raise RuntimeError("未配置 WECOM_NOTICE_WEBHOOK_URL")

    request = Request(
        WEBHOOK_URL,
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


def send_text(message: str, recipients: list[dict[str, str]], mention_all: bool = False) -> dict:
    """
    发送企业微信文本消息。

    Args:
        message: 消息内容
        recipients: 收件人列表，每个元素包含 wecom_userid 或 mobile
        mention_all: 是否 @all（忽略 recipients，@群内所有人）
    """
    if mention_all:
        # @all：mentioned_list 包含 "@all" 字符串
        payload = {
            "msgtype": "text",
            "text": {
                "content": message,
                "mentioned_list": ["@all"],
            },
        }
    else:
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
    return _send_webhook(payload)


def send_markdown(content: str) -> dict:
    """
    发送企业微信 Markdown 消息（不支持 @）

    Args:
        content: Markdown 格式的消息内容
    """
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }
    return _send_webhook(payload)


def send_image(base64_content: str, md5: str) -> dict:
    """
    发送企业微信图片消息（不支持 @）

    Args:
        base64_content: 图片内容的 base64 编码
        md5: 图片内容的 md5 值
    """
    payload = {
        "msgtype": "image",
        "image": {
            "base64": base64_content,
            "md5": md5
        }
    }
    return _send_webhook(payload)


def send_news(articles: list[dict]) -> dict:
    """
    发送企业微信图文消息（不支持 @）

    Args:
        articles: 图文列表，每项包含 title, description, url, picurl
    """
    payload = {
        "msgtype": "news",
        "news": {
            "articles": articles
        }
    }
    return _send_webhook(payload)


def send_template_card(card_type: str, template_card: dict) -> dict:
    """
    发送企业微信模板卡片消息（不支持 @）

    Args:
        card_type: 卡片类型，如 'text_notice' 或 'news_notice'
        template_card: 卡片内容字典
    """
    payload = {
        "msgtype": "template_card",
        "template_card": {
            "card_type": card_type,
            **template_card
        }
    }
    return _send_webhook(payload)
