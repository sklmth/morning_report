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
import excel_to_image
import xlsx_fix
import text_report
from mail_client import MailFetcher
from wechat_sender import send_images, send_text, WeChatSendError


# ── 配置加载（优先 .env，回退环境变量）────────────────────────────────
def _env_any(keys, default=""):
    """按优先级返回第一个非空环境变量。"""
    for k in keys:
        v = os.environ.get(k)
        if v:
            return v
    return default


def load_config():
    # 优先加载项目根 .env；再尝试服务器 OpenClaw 的邮箱 .env
    root_env = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), ".env")
    if os.path.exists(root_env):
        _load_dotenv(root_env)
    # 服务器已配好的邮箱 .env（通过 MAIL_ENV_FILE 指向，或默认路径）
    mail_env = os.environ.get(
        "MAIL_ENV_FILE", "/root/.openclaw/tools/qq-mail-mcp/.env")
    if mail_env and os.path.exists(mail_env):
        _load_dotenv(mail_env)

    # 兼容两套变量名：本项目 QQ_EMAIL* / 服务器 QQ_MAIL_*
    cfg = {
        "email": _env_any(["QQ_EMAIL", "QQ_MAIL_USER"]),
        "password": _env_any(["QQ_EMAIL_PASSWORD", "QQ_MAIL_PASS"]),
        "imap_host": _env_any(["QQ_IMAP_HOST", "QQ_MAIL_IMAP_HOST"], "imap.qq.com"),
        "imap_port": int(_env_any(["QQ_IMAP_PORT", "QQ_MAIL_IMAP_PORT"], "993")),
        "mailbox": _env_any(["QQ_MAILBOX", "QQ_MAIL_MAILBOX"], "INBOX"),
        "poll_seconds": int(_env_any(["MAIL_POLL_SECONDS"], "300")),
        "font_path": _env_any(["REPORT_FONT_PATH"]) or None,
        "send_command": _env_any(
            ["OPENCLAW_SEND_COMMAND"],
            'openclaw message send --media "{image}" --message "{caption}"'),
        "send_text_command": _env_any(
            ["OPENCLAW_SEND_TEXT_COMMAND"],
            'openclaw message send --message "{caption}"'),
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
# 触发处理所需的关键附件：归类后至少含其中之一才处理
REQUIRED_KINDS = {"wanmei", "yingfu"}


def process_files(file_paths, cfg):
    if not file_paths:
        log("无可处理文件，跳过。")
        return

    inputs = report_core.classify_inputs(file_paths)
    if not inputs:
        log(f"附件未能归类（共 {len(file_paths)} 个），跳过：" +
            ", ".join(os.path.basename(p) for p in file_paths))
        return

    # 触发条件：必须含完美一单 或 营服报表 之一（或全部），否则不处理
    if not (REQUIRED_KINDS & set(inputs.keys())):
        log("附件中无『完美一单』或『营服报表』，不触发处理，跳过：" +
            ", ".join(os.path.basename(p) for p in file_paths))
        return

    log("归类结果：" + ", ".join(f"{k}={os.path.basename(v)}"
                              for k, v in inputs.items()))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_xlsx = os.path.join(OUTPUT_DIR, f"早会五张表_{stamp}.xlsx")

    written = report_core.build_report(inputs, out_xlsx)
    log(f"已生成结果 Excel：{out_xlsx}（写入 sheet：{', '.join(written)}）")

    # 修复 LibreOffice 无法识别的 _xlfn.XLOOKUP 等前缀（否则导图会出 #NAME?）
    try:
        n_fixed = xlsx_fix.fix_workbook_formulas(out_xlsx)
        if n_fixed:
            log(f"已修复 {n_fixed} 个 _xlfn 公式前缀（供 LibreOffice 求值）。")
    except Exception as e:
        log(f"[WARN] 公式前缀修复失败（不影响数据，仅可能影响LO出图）：{e}")

    # 渲染四张图：优先 LibreOffice（样式与原 Excel 一致），失败回退 PIL 自绘
    img_dir = os.path.join(IMAGE_DIR, stamp)
    images = None
    if excel_to_image.soffice_available():
        try:
            images = excel_to_image.export_regions(out_xlsx, img_dir)
            log(f"已用 LibreOffice 导出 {len(images)} 张图：" +
                ", ".join(os.path.basename(p) for _, p in images))
        except Exception as e:
            log(f"[WARN] LibreOffice 出图失败，回退 PIL：{e}")
            images = None
    if images is None:
        images = image_render.render_all(out_xlsx, img_dir,
                                         font_path=cfg["font_path"])
        log(f"已用 PIL 渲染 {len(images)} 张图：" +
            ", ".join(os.path.basename(p) for _, p in images))

    # 生成文字通报
    report_text = ""
    try:
        report_text = text_report.build_report_text(out_xlsx)
        txt_path = os.path.join(img_dir, "通报.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        log(f"已生成文字通报：{txt_path}")
    except Exception as e:
        log(f"[WARN] 文字通报生成失败：{e}")

    # 发送：先发四张图，再发文字通报
    try:
        sent = send_images(images, cfg["send_command"])
        log(f"已通过 OpenClaw 发送 {sent} 张图到微信。")
        if report_text:
            send_text(report_text, cfg["send_text_command"])
            log("已发送文字通报到微信。")
    except WeChatSendError as e:
        log(f"[WARN] 微信发送失败：{e}")
        log(f"  图片/通报已保存在：{img_dir}，可手动发送或检查发送命令。")


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
