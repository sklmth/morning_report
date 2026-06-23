"""
用 LibreOffice (headless + UNO) 把结果 Excel「模板1」sheet 的四个区域
分别导出为 PNG。样式与原 Excel 一致（LibreOffice 求值公式并按原格式渲染）。

实现方式（稳健，不依赖 Draw 的 insertTransferable）：
  对每个区域：
    1) 设置该区域为「打印区域」（PrintAreas）
    2) 用 PDF 导出过滤器导出仅含该区域的单页 PDF
    3) 用 pdftoppm（poppler-utils）或 pdf2image 把 PDF 转 PNG
  这样比「复制到 Draw 再导出」更稳定，比例也更接近文档渲染结果。

四个区域（模板1 单元格范围，已与真实模板核对）：
  图1 完美一单积分完成通报  → A1:R21
  图2 高装高套目标完成情况  → A33:F43
  图3 全光任务完成情况      → J33:N46
  图4 区县目标完成情况      → P33:T44

依赖：libreoffice-calc、python3-uno、poppler-utils（pdftoppm）。
对外接口：export_regions(result_xlsx, out_dir) -> [(标题, png), ...]
"""

import os
import shutil
import socket
import subprocess
import sys
import time

REGIONS = [
    ("完美一单积分完成通报", "模板1", "A1:R21", "01_perfect_points"),
    ("高装高套目标完成情况", "模板1", "A33:F43", "02_gaozhuang"),
    ("全光任务完成情况", "模板1", "J33:N46", "03_quanguang"),
    ("区县目标完成情况", "模板1", "P33:T44", "04_county"),
]

_SOFFICE_CANDIDATES = [
    os.environ.get("SOFFICE_BIN", ""),
    "soffice", "libreoffice",
    "/usr/bin/soffice", "/usr/bin/libreoffice",
    "/opt/libreoffice/program/soffice",
    "C:/Program Files/LibreOffice/program/soffice.exe",
    "C:/Program Files (x86)/LibreOffice/program/soffice.exe",
]

# PDF 转 PNG 的渲染 DPI（越大越清晰、文件越大）
PDF_DPI = int(os.environ.get("REPORT_PDF_DPI", "300"))

# 自动裁白边时保留的安全边距，默认不保留，避免发图四周出现白框。
# 如个别渠道裁切过紧，可通过 REPORT_AUTOCROP_PAD=2/4 临时加回少量边距。
AUTOCROP_PAD = int(os.environ.get("REPORT_AUTOCROP_PAD", "0"))

# 把接近白色的像素也视为背景，避免 PDF 抗锯齿产生的浅灰边缘影响裁剪。
AUTOCROP_WHITE_THRESHOLD = int(os.environ.get("REPORT_AUTOCROP_WHITE_THRESHOLD", "248"))


def _find_soffice():
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
    """导出四区域 PNG。返回 [(标题, png路径), ...]。失败抛 RuntimeError。"""
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
        return _uno_export_pdf(result_xlsx, out_dir, port, timeout)
    finally:
        if started and proc:
            try:
                proc.terminate(); proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


def _uno_export_pdf(result_xlsx, out_dir, port, timeout):
    try:
        import uno
        from com.sun.star.beans import PropertyValue
    except ImportError as e:
        raise RuntimeError(
            "无法 import uno。请安装 python3-uno 并用能访问它的 Python 运行。") from e

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

        for title, sheet_name, rng, basename in REGIONS:
            if not sheets.hasByName(sheet_name):
                continue
            sheet = sheets.getByName(sheet_name)
            cell_range = sheet.getCellRangeByName(rng)

            # 仅把该区域设为打印区域
            addr = cell_range.getRangeAddress()
            sheet.setPrintAreas((addr,))

            # 缩放到一页：设置页面样式 ScaleToPagesX/Y
            _fit_one_page(doc, sheet, pv)

            # 导出 PDF（只含打印区域）
            pdf_path = os.path.join(out_dir, basename + ".pdf")
            pdf_filter = pv("FilterName", "calc_pdf_Export")
            # 只导出当前 sheet：用 Selection 限定
            doc.getCurrentController().select(cell_range)
            doc.storeToURL(uno.systemPathToFileUrl(pdf_path), (
                pdf_filter,
                pv("Overwrite", True),
            ))

            # PDF → PNG
            png_path = os.path.join(out_dir, basename + ".png")
            if _pdf_to_png(pdf_path, png_path):
                results.append((title, png_path))
            # 清理 PDF
            try:
                os.remove(pdf_path)
            except OSError:
                pass

            # 清除打印区域，避免影响下一个
            sheet.setPrintAreas(())
    finally:
        doc.close(False)

    if not results:
        raise RuntimeError("LibreOffice 未导出任何图片（检查模板1 sheet 与区域）。")
    return results


def _fit_one_page(doc, sheet, pv):
    """把当前 sheet 的页面样式设为「缩放到 1 页宽 1 页高」，边距清零，避免白边。"""
    try:
        style_name = sheet.PageStyle
        page_styles = doc.StyleFamilies.getByName("PageStyles")
        if page_styles.hasByName(style_name):
            ps = page_styles.getByName(style_name)
            ps.setPropertyValue("ScaleToPagesX", 1)
            ps.setPropertyValue("ScaleToPagesY", 1)
            for prop in ("HeaderIsOn", "FooterIsOn"):
                try:
                    ps.setPropertyValue(prop, False)
                except Exception:
                    pass
            # 清零四个边距，彻底消除 PDF 白框
            for prop in ("TopMargin", "BottomMargin", "LeftMargin", "RightMargin"):
                try:
                    ps.setPropertyValue(prop, 0)
                except Exception:
                    pass
    except Exception:
        pass


def _pdf_to_png(pdf_path, png_path):
    """把单页 PDF 转 PNG。优先 pdftoppm，其次 pdf2image。"""
    # 方案1：pdftoppm（poppler-utils）
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        prefix = png_path[:-4] if png_path.endswith(".png") else png_path
        try:
            subprocess.run([
                pdftoppm, "-png", "-r", str(PDF_DPI),
                "-singlefile", "-cropbox", pdf_path, prefix,
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(png_path):
                _autocrop(png_path)
                return True
        except subprocess.CalledProcessError:
            pass

    # 方案2：pdf2image（依赖 poppler）
    try:
        from pdf2image import convert_from_path
        pages = convert_from_path(pdf_path, dpi=PDF_DPI)
        if pages:
            pages[0].save(png_path, "PNG")
            _autocrop(png_path)
            return True
    except Exception:
        pass

    return False


def _autocrop(png_path):
    """去掉 PNG 四周多余白边。用 ImageChops.difference 精确识别内容边界。"""
    try:
        from PIL import Image, ImageChops
        im = Image.open(png_path).convert("RGB")
        # 与纯白背景做差值，差值 > 阈值的像素为内容
        diff = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255)))
        diff = diff.point(lambda x: 255 if x > (255 - AUTOCROP_WHITE_THRESHOLD) else 0)
        bbox = diff.getbbox()
        if bbox:
            pad = max(0, AUTOCROP_PAD)
            l = max(0, bbox[0] - pad)
            t = max(0, bbox[1] - pad)
            r = min(im.width, bbox[2] + pad)
            b = min(im.height, bbox[3] + pad)
            im.crop((l, t, r, b)).save(png_path, "PNG")
    except Exception:
        pass


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
