"""
早会数据处理系统 - Web 服务入口（端口 8990）。

启动：python daily_report/web_server.py
    --no-poll   不启动后台邮件轮询（仅提供网页，手动上传）
    --once      启动时立即收一次邮件再常驻

依赖：标准库（http.server / threading / email / cgi）+ 项目自身 daily_report/ 模块
"""

import cgi
import io
import json
import mimetypes
import os
import sys
import threading
import time
import traceback
import urllib.parse
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# 确保 daily_report/ 在 Python 路径中
_SRC = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SRC)
sys.path.insert(0, _SRC)

from storage import ReportStore
import server as _srv
import zhengqi_web as _zq

# ── 全局单例（main() 注入）────────────────────────────────────────────
_cfg: dict = {}
_store: ReportStore = None  # type: ignore
_upload_dir = os.path.join(_ROOT, "runtime", "uploads")
_PAGE_SIZE = 20

# ── 辅助 ─────────────────────────────────────────────────────────────

def _safe_runtime_path(rel):
    """把 runtime/ 下的相对路径解析为绝对路径，防止路径穿越。"""
    base = os.path.join(_ROOT, "runtime")
    target = os.path.normpath(os.path.join(base, rel))
    if not target.startswith(base + os.sep) and target != base:
        return None
    return target if os.path.exists(target) else None


def _report_to_web(r):
    """把数据库行转成 Web 展示用的 dict（把绝对路径变成 /files/ 相对地址）。"""
    base = os.path.join(_ROOT, "runtime")

    def to_url(abs_path):
        if not abs_path:
            return ""
        try:
            rel = os.path.relpath(abs_path, base).replace("\\", "/")
            return "/files/" + rel
        except ValueError:
            return ""

    images = []
    for img in (r.get("images") or []):
        images.append({"title": img.get("title", ""), "url": to_url(img.get("path", ""))})

    return {
        "id": r["id"],
        "created_at": r["created_at"],
        "source": r["source"],
        "subject": r.get("subject") or "",
        "sender": r.get("sender") or "",
        "status": r["status"],
        "message": r.get("message") or "",
        "report_text": r.get("report_text") or "",
        "images": images,
        "output_xlsx_url": to_url(r.get("output_xlsx") or ""),
        "written_sheets": r.get("written_sheets") or [],
        "input_files": [os.path.basename(p) for p in (r.get("input_files") or [])],
    }


# ── HTML 片段 ────────────────────────────────────────────────────────

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;
  background:#0d1117;color:#e6edf3;min-height:100vh}
a{color:#58a6ff;text-decoration:none}
.container{max-width:860px;margin:0 auto;padding:16px}
h1{font-size:1.3rem;color:#c8a96e;padding:20px 0 12px}
h2{font-size:1rem;color:#8b949e;margin-bottom:12px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:14px}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:.75rem;font-weight:600}
.badge-success{background:#1a4731;color:#3fb950}
.badge-error{background:#3d1a1a;color:#f85149}
.badge-skipped{background:#1f2937;color:#8b949e}
.meta{font-size:.8rem;color:#8b949e;margin:6px 0 10px}
.btn{display:inline-block;padding:10px 20px;border-radius:6px;border:none;
  background:#21262d;color:#e6edf3;cursor:pointer;font-size:.9rem;touch-action:manipulation}
.btn-primary{background:#c8a96e;color:#0d1117;font-weight:600}
.btn:hover{opacity:.85}
.upload-zone{border:2px dashed #30363d;border-radius:8px;padding:24px;text-align:center;margin-bottom:16px}
.upload-zone input[type=file]{display:block;margin:12px auto;color:#8b949e;max-width:100%}
.img-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-top:12px}
.img-grid img{width:100%;border-radius:6px;border:1px solid #30363d}
.img-caption{font-size:.75rem;color:#8b949e;margin-top:4px;text-align:center}
pre{white-space:pre-wrap;word-break:break-all;background:#0d1117;border:1px solid #30363d;
  border-radius:6px;padding:14px;font-size:.8rem;line-height:1.6;color:#c9d1d9;margin-top:10px}
.row-link{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.no-records{color:#8b949e;text-align:center;padding:40px 0;font-size:.9rem}
/* 加载遮罩 */
#loading{display:none;position:fixed;inset:0;background:rgba(13,17,23,.88);
  z-index:999;flex-direction:column;align-items:center;justify-content:center;gap:18px}
#loading.show{display:flex}
.spinner{width:44px;height:44px;border:4px solid #30363d;border-top-color:#c8a96e;
  border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.loading-text{color:#c8a96e;font-size:.95rem}
.pagination{display:flex;justify-content:center;align-items:center;gap:8px;margin-top:16px;flex-wrap:wrap}
.pagination .btn{min-width:36px;text-align:center;padding:8px 12px}
.pagination .cur{background:#c8a96e;color:#0d1117;font-weight:600}
/* 移动端 */
@media(max-width:600px){
  h1{font-size:1.1rem}
  .btn{font-size:.9rem;padding:12px 16px}
  .btn-primary,.btn-poll{width:100%;text-align:center;display:block;margin-top:8px}
  .row-link{flex-direction:column;align-items:flex-start}
  .row-link .btn{width:100%;text-align:center;margin-top:8px}
  .img-grid{grid-template-columns:1fr}
  .container{padding:12px}
  .upload-zone{padding:20px 12px}
  .upload-zone input[type=file]{font-size:.9rem;width:100%}
  .card{padding:12px}
}
"""

_JS = """
(function(){
  var overlay=document.getElementById('loading');
  function showLoading(msg){
    overlay.querySelector('.loading-text').textContent=msg||'处理中，请稍候…';
    overlay.classList.add('show');
  }
  document.querySelectorAll('form').forEach(function(f){
    f.addEventListener('submit',function(){
      var isUpload=f.action&&f.action.indexOf('/upload')>-1;
      showLoading(isUpload?'正在处理文件，请稍候…':'正在收取邮件…');
    });
  });
})();
"""


def _page(title, body, extra_head=""):
    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{_CSS}</style>{extra_head}
</head><body>
<div id="loading"><div class="spinner"></div><div class="loading-text">处理中，请稍候…</div></div>
<div class="container">
<h1>早会数据处理系统</h1>
{body}
</div>
<script>{_JS}</script>
</body></html>"""


def _badge(status):
    cls = {"success": "badge-success", "error": "badge-error"}.get(status, "badge-skipped")
    label = {"success": "成功", "error": "失败", "skipped": "跳过"}.get(status, status)
    return f'<span class="badge {cls}">{label}</span>'


# ── HTTP Handler ────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 静默访问日志

    def _send(self, code, body, content_type="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/":
            self._handle_index()
        elif path.startswith("/report/"):
            rid = path[len("/report/"):]
            self._handle_detail(rid)
        elif path.startswith("/files/"):
            rel = path[len("/files/"):]
            self._handle_file(rel)
        elif path.startswith("/download_zip/"):
            rid = path[len("/download_zip/"):]
            self._handle_download_zip(rid)
        elif path == "/api/reports":
            self._handle_api_reports()
        elif path == "/zhengqi/latest":
            self._handle_zhengqi_download()
        else:
            self._send(404, "<h3>Not Found</h3>")

    def do_POST(self):
        path = self.path.rstrip("/")
        if path == "/upload":
            self._handle_upload()
        elif path == "/poll":
            self._handle_poll()
        elif path == "/zhengqi/upload":
            self._handle_zhengqi_upload()
        elif path == "/zhengqi/upload-rows":
            self._handle_zhengqi_upload_rows()
        else:
            self._send(404, "Not Found")

    # ── GET / ──
    def _handle_index(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        try:
            page = max(1, int(qs.get("page", ["1"])[0]))
        except (ValueError, TypeError):
            page = 1
        total = _store.count_reports()
        import math
        total_pages = max(1, math.ceil(total / _PAGE_SIZE))
        page = min(page, total_pages)
        offset = (page - 1) * _PAGE_SIZE
        reports = [_report_to_web(r) for r in _store.list_reports(_PAGE_SIZE, offset)]
        cards = ""
        if reports:
            for r in reports:
                src_label = {"mail": "邮件", "upload": "上传", "local": "本地"}.get(r["source"], r["source"])
                cards += f"""<div class="card">
  <div class="row-link">
    <div>{_badge(r['status'])}
      <span style="margin-left:8px;font-size:.85rem;color:#c9d1d9">{r['subject'] or '（无标题）'}</span>
    </div>
    <a class="btn" href="/report/{r['id']}">查看详情</a>
  </div>
  <div class="meta">{r['created_at']} &nbsp;|&nbsp; 来源：{src_label} &nbsp;|&nbsp; {r['message']}</div>
</div>"""
        else:
            cards = '<div class="no-records">暂无处理记录，请上传文件或等待邮件触发。</div>'

        # 政企家庭专项走访统计卡片
        zq_recv = _zq.last_received()
        if zq_recv:
            zq_meta = f"最后接收：{zq_recv.strftime('%Y-%m-%d %H:%M:%S')}（金山文档推送）"
            zq_btn = ('<a class="btn btn-primary" href="/zhengqi/latest">'
                      '⬇ 下载最新家庭专项走访统计</a>')
        else:
            zq_meta = "尚未收到金山文档推送的政企标准化信息收集表。"
            zq_btn = '<span class="btn" style="opacity:.5;cursor:not-allowed">暂无可下载数据</span>'
        zhengqi_card = f"""<div class="card">
  <h2>政企家庭专项走访统计</h2>
  <div class="meta">{zq_meta}</div>
  <div class="row-link">
    <span style="font-size:.85rem;color:#8b949e">按当前自然周（周一~周日）实时统计</span>
    {zq_btn}
  </div>
</div>"""

        upload_form = """<div class="card">
  <h2>手动上传处理</h2>
  <form method="post" action="/upload" enctype="multipart/form-data">
    <div class="upload-zone">
      <div style="color:#8b949e;font-size:.85rem">选择一个或多个 Excel 文件（营服报表 / 完美一单 / 商机管控 / 红黄牌）</div>
      <input type="file" name="files" accept=".xlsx,.xls" multiple required>
    </div>
    <button type="submit" class="btn btn-primary">开始处理</button>
  </form>
</div>"""

        poll_form = """<div style="margin-bottom:14px">
  <form method="post" action="/poll" style="display:inline">
    <button type="submit" class="btn btn-poll">立即收取邮件</button>
  </form>
</div>"""

        # 分页导航
        pagination = ""
        if total_pages > 1:
            parts = []
            if page > 1:
                parts.append(f'<a class="btn" href="/?page={page-1}">‹ 上一页</a>')
            # 显示最多 7 个页码
            start = max(1, page - 3)
            end = min(total_pages, start + 6)
            start = max(1, end - 6)
            for p in range(start, end + 1):
                cls = 'btn cur' if p == page else 'btn'
                parts.append(f'<a class="{cls}" href="/?page={p}">{p}</a>')
            if page < total_pages:
                parts.append(f'<a class="btn" href="/?page={page+1}">下一页 ›</a>')
            pagination = f'<div class="pagination">{"".join(parts)}<span style="color:#8b949e;font-size:.8rem">共 {total} 条</span></div>'

        body = zhengqi_card + upload_form + poll_form + cards + pagination
        self._send(200, _page("早会数据处理系统", body))

    # ── GET /report/<id> ──
    def _handle_detail(self, rid):
        try:
            r = _store.get_report(int(rid))
        except (ValueError, TypeError):
            r = None
        if not r:
            self._send(404, _page("未找到", "<p>记录不存在。</p>"))
            return
        r = _report_to_web(r)

        img_html = ""
        if r["images"]:
            imgs = "".join(
                f'<div><a href="{img["url"]}" target="_blank"><img src="{img["url"]}" loading="lazy" alt="{img["title"]}"></a>'
                f'<div class="img-caption">{img["title"]}</div></div>'
                for img in r["images"]
            )
            img_html = f'<div class="img-grid">{imgs}</div>'

        xlsx_link = ""
        if r["output_xlsx_url"]:
            xlsx_link = f'<p style="margin-top:10px"><a href="{r["output_xlsx_url"]}" class="btn">下载结果 Excel</a></p>'

        text_html = f"<pre>{r['report_text']}</pre>" if r["report_text"] else ""
        sheets = "、".join(r["written_sheets"]) if r["written_sheets"] else "—"
        src_label = {"mail": "邮件", "upload": "上传", "local": "本地"}.get(r["source"], r["source"])

        zip_link = ""
        if r["images"]:
            zip_link = f'<p style="margin-top:10px"><a href="/download_zip/{r["id"]}" class="btn btn-primary">⬇ 一键下载全部图片</a></p>'

        body = f"""<p><a href="/" class="btn" style="margin-bottom:12px">← 返回列表</a></p>
<div class="card">
  <div style="margin-bottom:8px">{_badge(r['status'])} <b style="margin-left:8px">{r['subject'] or '（无标题）'}</b></div>
  <div class="meta">
    时间：{r['created_at']} &nbsp;|&nbsp; 来源：{src_label}<br>
    发件人：{r['sender'] or '—'} &nbsp;|&nbsp; Sheet：{sheets}<br>
    {r['message']}
  </div>
  {img_html}
  {zip_link}
  {xlsx_link}
  {text_html}
</div>"""
        self._send(200, _page(f"详情 #{r['id']}", body))

    # ── GET /files/<rel> ──
    def _handle_file(self, rel):
        rel = urllib.parse.unquote(rel)
        abs_path = _safe_runtime_path(rel)
        if not abs_path:
            self._send(404, "Not Found")
            return
        mime, _ = mimetypes.guess_type(abs_path)
        mime = mime or "application/octet-stream"
        with open(abs_path, "rb") as f:
            data = f.read()
        self._send(200, data, mime)

    # ── GET /download_zip/<id> ──
    def _handle_download_zip(self, rid):
        try:
            r = _store.get_report(int(rid))
        except (ValueError, TypeError):
            r = None
        if not r:
            self._send(404, "Not Found")
            return
        r = _report_to_web(r)
        buf = io.BytesIO()
        base = os.path.join(_ROOT, "runtime")
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for img in r["images"]:
                url = img["url"]
                if not url.startswith("/files/"):
                    continue
                rel = urllib.parse.unquote(url[len("/files/"):])
                abs_path = _safe_runtime_path(rel)
                if abs_path:
                    zf.write(abs_path, os.path.basename(abs_path))
        data = buf.getvalue()
        fname = f"report_{rid}_images.zip"
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ── GET /api/reports ──
    def _handle_api_reports(self):
        reports = [_report_to_web(r) for r in _store.list_reports(50)]
        self._send_json(reports)

    # ── POST /upload ──
    def _handle_upload(self):
        try:
            ctype = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            environ = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": ctype,
                "CONTENT_LENGTH": str(length),
            }
            form = cgi.FieldStorage(fp=io.BytesIO(raw), environ=environ,
                                    headers=self.headers, keep_blank_values=True)
            files_field = form["files"]
            if not isinstance(files_field, list):
                files_field = [files_field]

            os.makedirs(_upload_dir, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            saved_paths = []
            for item in files_field:
                if not item.filename:
                    continue
                fname = f"{stamp}_{item.filename}"
                dest = os.path.join(_upload_dir, fname)
                with open(dest, "wb") as f:
                    f.write(item.file.read())
                saved_paths.append(dest)

            if not saved_paths:
                self._redirect("/?err=no_file")
                return

            result = _srv.process_files(saved_paths, _cfg, send_wechat=False)
            _store.add_report(source="upload", subject="手动上传", **result)
            self._redirect("/")
        except Exception as e:
            traceback.print_exc()
            self._redirect(f"/?err={urllib.parse.quote(str(e))}")

    # ── POST /poll ──
    def _handle_poll(self):
        try:
            _srv.poll_once(_cfg, store=_store)
        except Exception as e:
            traceback.print_exc()
        self._redirect("/")

    # ── POST /zhengqi/upload ── 金山文档脚本推送政企标准化信息收集表
    def _handle_zhengqi_upload(self):
        """接收原始 Excel。支持 multipart（字段名 file/files）或 raw body（application/*）。

        成功返回 JSON：{ok, received, generated, rows}
        """
        try:
            ctype = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)

            filename = "input.xlsx"
            data = None
            if "multipart/form-data" in ctype:
                environ = {"REQUEST_METHOD": "POST", "CONTENT_TYPE": ctype,
                           "CONTENT_LENGTH": str(length)}
                form = cgi.FieldStorage(fp=io.BytesIO(raw), environ=environ,
                                        headers=self.headers, keep_blank_values=True)
                field = form["file"] if "file" in form else (
                    form["files"] if "files" in form else None)
                if isinstance(field, list):
                    field = field[0] if field else None
                if field is not None and getattr(field, "filename", None):
                    filename = field.filename
                    data = field.file.read()
            else:
                # raw body：直接就是 xlsx 字节
                data = raw

            if not data:
                self._send_json({"ok": False, "error": "未收到文件内容"}, 400)
                return

            _zq.save_input(data, original_name=filename)
            df, out_path = _zq.generate()
            # 数据行数（去掉合计行）
            n = max(0, len(df) - 1)
            self._send_json({
                "ok": True,
                "received": filename,
                "generated": os.path.basename(out_path),
                "rows": n,
            })
        except Exception as e:
            traceback.print_exc()
            self._send_json({"ok": False, "error": str(e)}, 500)

    # ── POST /zhengqi/upload-rows ── AirScript/金山文档脚本推送 JSON 行
    def _handle_zhengqi_upload_rows(self):
        """接收 JSON 行数据（AirScript 读单元格拼成的数组）。

        请求体 application/json，两种形态均可：
            {"rows": [ {...}, ... ], "file_name": "可选"}
            [ {...}, ... ]                      # 直接就是数组

        每行至少含 name/type/appt_date/result（或对应中文表头名）。
        成功返回 {ok, received, generated, rows}。
        """
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._send_json({"ok": False, "error": "请求体不是合法 JSON"}, 400)
                return

            if isinstance(payload, list):
                rows = payload
                filename = "rows"
            elif isinstance(payload, dict):
                rows = payload.get("rows")
                filename = payload.get("file_name") or "rows"
            else:
                rows = None
                filename = "rows"

            if not isinstance(rows, list) or not rows:
                self._send_json({"ok": False, "error": "缺少 rows 数组或为空"}, 400)
                return

            _zq.save_rows(rows, original_name=filename)
            df, out_path = _zq.generate()
            n = max(0, len(df) - 1)  # 去掉合计行
            self._send_json({
                "ok": True,
                "received": filename,
                "generated": os.path.basename(out_path),
                "rows": n,
            })
        except Exception as e:
            traceback.print_exc()
            self._send_json({"ok": False, "error": str(e)}, 500)

    # ── GET /zhengqi/latest ── 下载最新统计结果（按当天口径实时生成）
    def _handle_zhengqi_download(self):
        try:
            if not _zq.has_input():
                self._send(404, _page("暂无数据", "<p>尚未收到政企标准化信息收集表。</p>"))
                return
            _df, out_path = _zq.generate()
            with open(out_path, "rb") as f:
                data = f.read()
            fname = os.path.basename(out_path)
            quoted = urllib.parse.quote(fname)
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header(
                "Content-Disposition",
                f"attachment; filename*=UTF-8''{quoted}")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            traceback.print_exc()
            self._send(500, _page("生成失败", f"<p>生成失败：{e}</p>"))


# ── 后台邮件轮询线程 ────────────────────────────────────────────────

def _bg_poll_loop(cfg, store):
    while True:
        try:
            _srv.poll_once(cfg, store=store)
        except Exception:
            traceback.print_exc()
        secs = _srv.current_poll_seconds(cfg)
        time.sleep(secs)


# ── 入口 ────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="早会数据处理 Web 服务")
    parser.add_argument("--no-poll", action="store_true", help="不启动后台邮件轮询")
    parser.add_argument("--once", action="store_true", help="启动时立即收一次邮件")
    args = parser.parse_args()

    _srv._load_dotenv  # 触发模块级副作用
    cfg = _srv.load_config()
    global _cfg, _store
    _cfg = cfg
    _store = ReportStore(cfg["db_path"])

    if args.once:
        _srv.poll_once(cfg, store=_store)

    if not args.no_poll:
        t = threading.Thread(target=_bg_poll_loop, args=(cfg, _store), daemon=True)
        t.start()
        print(f"[web] 后台邮件轮询已启动，间隔 {_srv.current_poll_seconds(cfg)}s")

    host, port = cfg["web_host"], cfg["web_port"]
    httpd = HTTPServer((host, port), Handler)
    print(f"[web] 服务已启动：http://{host}:{port}/")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
