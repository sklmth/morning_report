"""
QQ 邮箱收件（IMAP）：轮询未读邮件，下载 Excel 附件到本地。

服务器版自动流程的入口数据源。QQ 邮箱 IMAP/SMTP 已连通，授权码方式登录。
"""

import os
import re
import email
import imaplib
import time
from email.header import decode_header


def _decode_str(s):
    if not s:
        return ""
    parts = decode_header(s)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(enc or "utf-8", errors="replace"))
            except (LookupError, TypeError):
                out.append(text.decode("utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _safe_filename(name):
    name = _decode_str(name)
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip()


class MailFetcher:
    def __init__(self, host, port, user, password, mailbox="INBOX"):
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.mailbox = mailbox

    def _connect(self):
        conn = imaplib.IMAP4_SSL(self.host, self.port)
        conn.login(self.user, self.password)
        # QQ 邮箱需要 ID 命令，否则可能报 Unsafe Login
        try:
            args = ("name", "morning-report", "contact", self.user,
                    "version", "1.0", "vendor", "python-imaplib")
            typ, _ = conn._simple_command("ID", '("' + '" "'.join(args) + '")')
            conn._untagged_response(typ, [None], "ID")
        except Exception:
            pass
        conn.select(self.mailbox)
        return conn

    def fetch_unseen_attachments(self, save_dir, exts=(".xlsx", ".xls"),
                                 mark_seen=True):
        """
        拉取所有未读邮件中的 Excel 附件，下载到 save_dir。

        返回：list of dict，每封含附件的邮件一个：
            { "subject": ..., "from": ..., "files": [本地路径, ...] }
        """
        os.makedirs(save_dir, exist_ok=True)
        conn = self._connect()
        results = []
        try:
            typ, data = conn.search(None, "UNSEEN")
            if typ != "OK":
                return results
            ids = data[0].split()
            for num in ids:
                typ, msg_data = conn.fetch(num, "(RFC822)")
                if typ != "OK":
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                subject = _decode_str(msg.get("Subject"))
                sender = _decode_str(msg.get("From"))

                saved = []
                for part in msg.walk():
                    if part.get_content_maintype() == "multipart":
                        continue
                    filename = part.get_filename()
                    if not filename:
                        continue
                    filename = _safe_filename(filename)
                    if not filename.lower().endswith(exts):
                        continue
                    payload = part.get_payload(decode=True)
                    if not payload:
                        continue
                    dest = os.path.join(save_dir, filename)
                    # 同名去重
                    base, ext = os.path.splitext(dest)
                    k = 1
                    while os.path.exists(dest):
                        dest = f"{base}_{k}{ext}"
                        k += 1
                    with open(dest, "wb") as f:
                        f.write(payload)
                    saved.append(dest)

                if saved:
                    results.append({"subject": subject, "from": sender,
                                    "files": saved})
                    if mark_seen:
                        conn.store(num, "+FLAGS", "\\Seen")
        finally:
            try:
                conn.close()
            except Exception:
                pass
            conn.logout()
        return results
