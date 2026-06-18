"""
通过 OpenClaw 把图片发到微信。

按配置的命令行模板调用（默认 `openclaw message send --media ... --message ...`），
命令可在 .env 的 OPENCLAW_SEND_COMMAND 中覆盖，便于适配不同部署。
"""

import json
import re
import shlex
import subprocess


class WeChatSendError(Exception):
    pass


class SendResult:
    def __init__(self, stdout, stderr, message_id=None):
        self.stdout = stdout.strip()
        self.stderr = stderr.strip()
        self.message_id = message_id

    @property
    def output(self):
        return "\n".join(p for p in [self.stdout, self.stderr] if p).strip()


def send_image(image_path, caption, command_template, timeout=120):
    """
    发送单张图片。

        command_template: 形如
            openclaw message send --media "{image}" --message "{caption}"
          支持占位符 {image} {caption}
    """
    args = _build_args(command_template, {
        "image": image_path,
        "caption": caption or "",
    })
    result = _run_send(args, timeout=timeout)
    return result


def send_images(images, command_template, timeout=120):
    """
    批量发送。images: [(caption, image_path), ...]
    返回成功发送的 SendResult 列表；任一失败抛出异常。
    """
    results = []
    for caption, path in images:
        results.append(send_image(path, caption, command_template, timeout=timeout))
    return results


def send_text(text, command_template, timeout=120):
    """
    发送纯文字消息。command_template 形如
        openclaw message send --message "{caption}"
    支持占位符 {caption}。文字通过临时文件传递以避免命令行长度/转义问题时，
    可在命令模板中使用 {caption}（此处直接替换）。
    """
    args = _build_args(command_template, {"caption": text or ""})
    result = _run_send(args, timeout=timeout)
    return result


def _run_send(args, timeout=120):
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError as e:
        raise WeChatSendError(f"找不到发送命令：{e}") from e
    except subprocess.TimeoutExpired as e:
        raise WeChatSendError(f"发送超时：{e}") from e

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    output = "\n".join(p for p in [stdout.strip(), stderr.strip()] if p)
    if proc.returncode != 0:
        raise WeChatSendError(f"发送失败 (code={proc.returncode})：{output}")

    message_id = _extract_message_id(output)
    if not message_id:
        raise WeChatSendError(
            "发送命令返回成功，但未检测到 OpenClaw/微信 Message ID；"
            f"为避免误判送达，按失败处理。输出：{output or '<empty>'}")
    return SendResult(stdout, stderr, message_id=message_id)


def _extract_message_id(output):
    """从 OpenClaw CLI 输出中提取真实发送回执的 message id。"""
    # Human output: ✅ Sent via openclaw-weixin. Message ID: openclaw-weixin:...
    match = re.search(r"Message ID:\s*([^\s]+)", output)
    if match:
        return match.group(1).strip()

    # JSON output variants, if command template later adds --json.
    decoder = json.JSONDecoder()
    for i, ch in enumerate(output):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(output[i:])
        except json.JSONDecodeError:
            continue
        found = _find_message_id(obj)
        if found:
            return found
    return None


def _find_message_id(value):
    if isinstance(value, dict):
        for key in ("messageId", "message_id", "id"):
            v = value.get(key)
            if isinstance(v, str) and v:
                return v
        for v in value.values():
            found = _find_message_id(v)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_message_id(item)
            if found:
                return found
    return None


def _is_windows():
    import os
    return os.name == "nt"


def _build_args(command_template, values):
    """
    先拆命令模板，再替换占位符。

    这样 caption 中的换行、引号等字符不会破坏 shlex 对命令模板的解析，
    subprocess.run(list) 也不会经过 shell 二次解释。
    """
    try:
        parts = shlex.split(command_template, posix=(not _is_windows()))
    except ValueError as e:
        raise WeChatSendError(f"发送命令模板解析失败：{e}") from e
    for key, value in values.items():
        placeholder = "{" + key + "}"
        parts = [p.replace(placeholder, value) for p in parts]
    return parts
