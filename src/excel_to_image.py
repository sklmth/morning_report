"""
用 LibreOffice 把结果 Excel「模板1」sheet 的四个区域分别导出为 PNG。
样式与原 Excel 完全一致（LibreOffice 求值公式并按原格式渲染）。

实现方式：Python-UNO（连接 headless soffice socket）。导出每个区域的做法是
复制选区到一个临时 Draw 文档，再用 GraphicExportFilter 导出 PNG —— 这样能保留
单元格的颜色、边框、合并、数字格式、条件格式与数据条。

四个区域（模板1 单元格范围，已与真实模板核对）：
  图1 完美一单积分完成通报  → A1:R21
  图2 高装高套目标完成情况  → A33:F43
  图3 全光任务完成情况      → J33:N46
  图4 区县目标完成情况      → P33:T44

依赖：服务器安装 libreoffice + python3-uno。
对外接口：export_regions(result_xlsx, out_dir) -> [(标题, png), ...]
"""

import os
import socket
import subprocess
import sys
import time

REGIONS = [
    ("完美一单积分完成通报", "模板1", "A1:R21", "01_perfect_points.png"),
    ("高装高套目标完成情况", "模板1", "A33:F43", "02_gaozhuang.png"),
    ("全光任务完成情况", "模板1", "J33:N46", "03_quanguang.png"),
    ("区县目标完成情况", "模板1", "P33:T44", "04_county.png"),
]

_SOFFICE_CANDIDATES = [
    os.environ.get("SOFFICE_BIN", ""),
    "soffice", "libreoffice",
    "/usr/bin/soffice", "/usr/bin/libreoffice",
    "/opt/libreoffice/program/soffice",
    "C:/Program Files/LibreOffice/program/soffice.exe",
    "C:/Program Files (x86)/LibreOffice/program/soffice.exe",
]


def _find_soffice():
    import shutil
    for c in _SOFFICE_CANDIDATES:
        if not c:
            continue
        if os.path.isabs(c) and os.path.exists(c):
            return c
        found = shutil.which(c)
        if found:
            return found
    return None


def soffice_available():
    return _find_soffice() is not None


def _port_open(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def export_regions(result_xlsx, out_dir, port=2002, timeout=120):
    """
    导出四区域 PNG。返回 [(标题, png路径), ...]。
    LibreOffice 不可用或 UNO 失败时抛 RuntimeError，调用方可回退。
    """
    soffice = _find_soffice()
    if not soffice:
        raise RuntimeError("未找到 LibreOffice (soffice)。")

    os.makedirs(out_dir, exist_ok=True)
    result_xlsx = os.path.abspath(result_xlsx)
    out_dir = os.path.abspath(out_dir)

    proc = None
    started = False
    if not _port_open("localhost", port):
        proc = subprocess.Popen([
            soffice, "--headless", "--norestore", "--invisible",
            "--nodefault", "--nologo", "--nofirststartwizard",
            f"--accept=socket,host=localhost,port={port};urp;",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        started = True

    try:
        return _uno_export(result_xlsx, out_dir, port, timeout)
    finally:
        if started and proc:
            try:
                proc.terminate(); proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


def _uno_export(result_xlsx, out_dir, port, timeout):
    try:
        import uno
        from com.sun.star.beans import PropertyValue
    except ImportError as e:
        raise RuntimeError(
            "无法 import uno。请用 LibreOffice 自带 python 运行本流程，"
            "或安装 python3-uno（apt-get install python3-uno）。") from e

    local_ctx = uno.getComponentContext()
    resolver = local_ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_ctx)

    ctx = None
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            ctx = resolver.resolve(
                f"uno:socket,host=localhost,port={port};urp;"
                "StarOffice.ComponentContext")
            break
        except Exception as e:
            last_err = e
            time.sleep(1)
    if ctx is None:
        raise RuntimeError(f"连接 LibreOffice UNO 失败：{last_err}")

    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)

    def pv(name, value):
        p = PropertyValue(); p.Name = name; p.Value = value
        return p

    url = uno.systemPathToFileUrl(result_xlsx)
    doc = desktop.loadComponentFromURL(url, "_blank", 0, (pv("Hidden", True),))

    results = []
    try:
        try:
            doc.calculateAll()
        except Exception:
            pass

        sheets = doc.Sheets
        controller = doc.getCurrentController()

        for title, sheet_name, rng, fname in REGIONS:
            if not sheets.hasByName(sheet_name):
                continue
            sheet = sheets.getByName(sheet_name)
            cell_range = sheet.getCellRangeByName(rng)
            controller.setActiveSheet(sheet)
            controller.select(cell_range)
            transferable = controller.getTransferable()

            draw = desktop.loadComponentFromURL(
                "private:factory/sdraw", "_blank", 0, (pv("Hidden", True),))
            try:
                dctrl = draw.getCurrentController()
                dctrl.insertTransferable(transferable)
                page = draw.DrawPages.getByIndex(0)
                if page.Count == 0:
                    continue
                shape = page.getByIndex(0)
                exporter = smgr.createInstanceWithContext(
                    "com.sun.star.drawing.GraphicExportFilter", ctx)
                exporter.setSourceDocument(shape)
                png = os.path.join(out_dir, fname)
                exporter.filter((
                    pv("URL", uno.systemPathToFileUrl(png)),
                    pv("MediaType", "image/png"),
                ))
                if os.path.exists(png):
                    results.append((title, png))
            finally:
                draw.close(False)
    finally:
        doc.close(False)

    if not results:
        raise RuntimeError("LibreOffice 未导出任何图片（检查模板1 sheet 与区域）。")
    return results


if __name__ == "__main__":
    import glob
    files = sorted(glob.glob(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "runtime", "output", "*.xlsx")))
    if not files:
        print("无结果 Excel，请先运行 server.py --local")
        sys.exit(1)
    out = os.path.join(os.path.dirname(os.path.dirname(files[-1])),
                       "lo_images")
    for t, p in export_regions(files[-1], out):
        print(t, "->", p)
