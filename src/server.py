"""
云服务器无界面版主程序。

流程：
  轮询 QQ 邮箱未读邮件 → 下载 Excel 附件（1 个或多个均可）
  → 归类（完美一单 / 营服报表 / 商机管控 …）
  → 写入模板生成结果 Excel
  → 从结果 Excel 重算并渲染四张通报图
  → 通过 OpenClaw 把四张图依次发到微信

运行：
  python src/server.py            # 持续轮询（间隔取 MAIL_POLL_SECONDS）
  python src/server.py --once     # 只跑一轮
  python src/server.py --local 文件1.xlsx 文件2.xlsx   # 跳过邮箱，直接处理本地文件

配置：复制 .env.example 为 .env 并填写，或直接用环境变量。
"""

import os
import sys
import time
import argparse
import traceback
from datetime import datetime

# 让 src 内模块可直接 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import report_core
import image_render
from mail_client import MailFetcher
from wechat_sender import send_images, WeChatSendError


# ── 配置加载（优先 .env，回退环境变量）────────────────────────────────
def load_config():
    env_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        _load_dotenv(env_path)

    cfg = {
        "email": os.environ.get("QQ_EMAIL", ""),
        "password": os.environ.get("QQ_EMAIL_PASSWORD", ""),
        "imap_host": os.environ.get("QQ_IMAP_HOST", "imap.qq.com"),
        "imap_port": int(os.environ.get("QQ_IMAP_PORT", "993")),
        "mailbox": os.environ.get("QQ_MAILBOX", "INBOX"),
        "poll_seconds": int(os.environ.get("MAIL_POLL_SECONDS", "300")),
        "font_path": os.environ.get("REPORT_FONT_PATH", "") or None,
        "send_command": os.environ.get(
            "OPENCLAW_SEND_COMMAND",
            'openclaw message send --media "{image}" --message "{caption}"'),
    }
    return cfg


def _load_dotenv(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


# ── 目录 ──────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(ROOT, "runtime")
INBOX_DIR = os.path.join(RUNTIME_DIR, "inbox")
OUTPUT_DIR = os.path.join(RUNTIME_DIR, "output")
IMAGE_DIR = os.path.join(RUNTIME_DIR, "images")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        # Windows GBK 控制台对部分字符（如 emoji）无法编码，降级输出
        enc = (sys.stdout.encoding or "utf-8")
        sys.stdout.buffer.write(line.encode(enc, errors="replace") + b"\n")
        sys.stdout.flush()


# ── 单批处理：从一组文件出图并发送 ────────────────────────────────────
def process_files(file_paths, cfg):
    if not file_paths:
        log("无可处理文件，跳过。")
        return

    inputs = report_core.classify_inputs(file_paths)
    if not inputs:
        log(f"附件未能归类（共 {len(file_paths)} 个），跳过：" +
            ", ".join(os.path.basename(p) for p in file_paths))
        return

    log("归类结果：" + ", ".join(f"{k}={os.path.basename(v)}"
                              for k, v in inputs.items()))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_xlsx = os.path.join(OUTPUT_DIR, f"早会五张表_{stamp}.xlsx")

    written = report_core.build_report(inputs, out_xlsx)
    log(f"已生成结果 Excel：{out_xlsx}（写入 sheet：{', '.join(written)}）")

    img_dir = os.path.join(IMAGE_DIR, stamp)
    images = image_render.render_all(out_xlsx, img_dir, font_path=cfg["font_path"])
    log(f"已渲染 {len(images)} 张图：" +
        ", ".join(os.path.basename(p) for _, p in images))

    try:
        sent = send_images(images, cfg["send_command"])
        log(f"已通过 OpenClaw 发送 {sent} 张图到微信。")
    except WeChatSendError as e:
        log(f"[WARN] 微信发送失败：{e}")
        log(f"  图片已保存在：{img_dir}，可手动发送或检查 OPENCLAW_SEND_COMMAND。")


# ── 一轮邮件轮询 ──────────────────────────────────────────────────────
def poll_once(cfg):
    if not cfg["email"] or not cfg["password"]:
        log("未配置 QQ_EMAIL / QQ_EMAIL_PASSWORD，无法收信。")
        return
    fetcher = MailFetcher(cfg["imap_host"], cfg["imap_port"],
                          cfg["email"], cfg["password"], cfg["mailbox"])
    try:
        batches = fetcher.fetch_unseen_attachments(INBOX_DIR)
    except Exception as e:
        log(f"[WARN] 收信失败：{e}")
        return

    if not batches:
        log("无新邮件附件。")
        return

    for b in batches:
        log(f"新邮件：{b['subject']}（来自 {b['from']}），"
            f"附件 {len(b['files'])} 个。")
        try:
            process_files(b["files"], cfg)
        except Exception as e:
            log(f"[WARN] 处理出错：{e}")
            traceback.print_exc()


# ── 入口 ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="早会数据处理 - 服务器版")
    parser.add_argument("--once", action="store_true", help="只轮询一轮后退出")
    parser.add_argument("--local", nargs="+", metavar="FILE",
                        help="跳过邮箱，直接处理本地 Excel 文件")
    args = parser.parse_args()

    cfg = load_config()

    if args.local:
        log("本地模式：直接处理指定文件。")
        process_files([os.path.abspath(p) for p in args.local], cfg)
        return

    if args.once:
        poll_once(cfg)
        return

    log(f"服务启动，轮询间隔 {cfg['poll_seconds']}s，邮箱 {cfg['email']}。")
    while True:
        try:
            poll_once(cfg)
        except KeyboardInterrupt:
            log("收到中断，退出。")
            break
        except Exception as e:
            log(f"[WARN] 轮询异常：{e}")
            traceback.print_exc()
        time.sleep(cfg["poll_seconds"])


if __name__ == "__main__":
    main()
