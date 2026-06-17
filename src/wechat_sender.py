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
    args = _build_args(command_template, {
        "image": image_path,
        "caption": caption or "",
    })
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
    args = _build_args(command_template, {"caption": text or ""})
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
