"""
通过 OpenClaw 把图片发到微信。

按配置的命令行模板调用（默认 `openclaw message send --media ... --message ...`），
命令可在 .env 的 OPENCLAW_SEND_COMMAND 中覆盖，便于适配不同部署。
"""

import shlex
import subprocess


class WeChatSendError(Exception):
    pass


def send_image(image_path, caption, command_template, timeout=120):
    """
    发送单张图片。

        command_template: 形如
            openclaw message send --media "{image}" --message "{caption}"
          支持占位符 {image} {caption}
    """
    cmd_str = command_template.replace("{image}", image_path).replace(
        "{caption}", caption or "")
    # Windows 与 Linux 都用 shell 拆分，保留引号语义
    try:
        args = shlex.split(cmd_str, posix=(not _is_windows()))
    except ValueError:
        args = cmd_str
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError as e:
        raise WeChatSendError(f"找不到发送命令：{e}") from e
    except subprocess.TimeoutExpired as e:
        raise WeChatSendError(f"发送超时：{e}") from e
    if proc.returncode != 0:
        raise WeChatSendError(
            f"发送失败 (code={proc.returncode})：{proc.stderr or proc.stdout}")
    return proc.stdout.strip()


def send_images(images, command_template, timeout=120):
    """
    批量发送。images: [(caption, image_path), ...]
    返回成功发送的数量；任一失败抛出异常并附带已发送数。
    """
    sent = 0
    for caption, path in images:
        send_image(path, caption, command_template, timeout=timeout)
        sent += 1
    return sent


def send_text(text, command_template, timeout=120):
    """
    发送纯文字消息。command_template 形如
        openclaw message send --message "{caption}"
    支持占位符 {caption}。文字通过临时文件传递以避免命令行长度/转义问题时，
    可在命令模板中使用 {caption}（此处直接替换）。
    """
    cmd_str = command_template.replace("{caption}", text or "")
    try:
        args = shlex.split(cmd_str, posix=(not _is_windows()))
    except ValueError:
        args = cmd_str
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError as e:
        raise WeChatSendError(f"找不到发送命令：{e}") from e
    except subprocess.TimeoutExpired as e:
        raise WeChatSendError(f"发送超时：{e}") from e
    if proc.returncode != 0:
        raise WeChatSendError(
            f"发送失败 (code={proc.returncode})：{proc.stderr or proc.stdout}")
    return proc.stdout.strip()


def _is_windows():
    import os
    return os.name == "nt"
