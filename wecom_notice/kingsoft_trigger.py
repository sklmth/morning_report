"""金山文档webhook触发器 - 定时触发金山文档自动化流程"""

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from wecom_notice.config import KINGSOFT_WEBHOOK_URL

logger = logging.getLogger(__name__)


def trigger_kingsoft_data_sync() -> dict:
    """
    触发金山文档webhook，让金山文档执行AirScript脚本上传数据。

    金山文档收到webhook请求后会：
    1. 执行配置的AirScript脚本
    2. 脚本读取多维表格数据
    3. 脚本POST数据到服务器 /api/airscript/upload

    Returns:
        dict: 金山文档webhook响应
    """
    if not KINGSOFT_WEBHOOK_URL:
        raise RuntimeError("未配置 KINGSOFT_WEBHOOK_URL")

    logger.info(f"触发金山文档数据同步: {KINGSOFT_WEBHOOK_URL}")

    # 金山文档webhook可能需要特定的请求参数，根据你的配置调整
    payload = {
        "trigger_source": "server_scheduler",
        "action": "sync_data"
    }

    request = Request(
        KINGSOFT_WEBHOOK_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            logger.info(f"金山文档webhook响应: {body}")

    except HTTPError as exc:
        error_body = exc.read().decode('utf-8', 'replace')
        logger.error(f"金山文档webhook请求失败: HTTP {exc.code} {error_body}")
        raise RuntimeError(f"金山文档webhook请求失败: HTTP {exc.code}") from exc

    except URLError as exc:
        logger.error(f"金山文档webhook网络请求失败: {exc.reason}")
        raise RuntimeError(f"金山文档webhook网络请求失败: {exc.reason}") from exc

    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        # 金山文档可能返回非JSON响应
        result = {"raw_response": body}

    return result
