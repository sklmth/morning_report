"""
四张通报图渲染（服务器版，纯 Python + PIL，无需 Excel/LibreOffice）。

四张图对应「模板1」中的四个区域，但模板靠公式计算，服务器无 Excel 无法求值，
因此这里用 Python 直接从结果 Excel 的各数据 sheet 重算同样口径，再用 PIL 画成表格图：

  图1 完美一单积分完成通报   ← 完美一单 / 高套 / 全光组网 / 激励 等（团队维度）
  图2 高装高套目标完成情况   ← 高装高套（姓名+高套数+目标）
  图3 全光任务完成情况       ← 交付高装（智云工程师/高端装维 协同主从网关数 vs 目标）
  图4 区县目标完成情况       ← 高套 sheet 中各区县短名 + 区县目标

口径与「模板1」公式保持一致；如模板调整，请同步本文件。
"""

import os
from datetime import date, timedelta

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# ── 团队/区县/目标等常量（与模板1 中硬编码一致）──────────────────────
PERFECT_POINT_TARGET = 2500          # 每人完美一单积分目标（模板 J 列）
PERFECT_TEAM_TOTAL_TARGET = 35000    # 合计目标（模板 J20）

# 党政军团队 / 大企业团队 成员（顺序与模板 B4:B18 一致）
TEAM_PARTY = ["麦海芬", "黄淡妮", "邱海燕", "李东", "王锦添", "黄观霞", "潘观友"]
TEAM_ENTERPRISE = ["伍颖敏", "谢卓和", "冯艺康", "李玉强", "张小敏", "具进康", "钟俊杰"]

# 全光任务完成情况（图3）：智云工程师 + 高端装维，姓名→发展目标（模板 交付高装 C 列）
# 注意：模板「主从网关数」并非按本人姓名直接匹配全光组网，而是经「交付高装」协同映射：
#   智云工程师 本人「主从网关数」= Σ(全光组网[客户经理] 当其 协同交付经理==本人)
#   高端装维   本人「主从网关数」= Σ(全光组网[客户经理] 当其 装维协同结对==本人)
# 协同映射来自「交付高装」J(客户经理)/K(装维协同)/M(协同交付经理) 列，运行时直接读取，
# 不在代码内硬编码，确保与模板一致。
QUANGUANG_TARGETS = [
    ("智云工程师", "零橹", 84),
    ("智云工程师", "何而恒", 84),
    ("智云工程师", "魏垚恒", 84),
    ("智云工程师", "吴文懿", 61),
    ("高端装维", "陈梓铭", 42),
    ("高端装维", "程庆德", 42),
    ("高端装维", "刘奇峻", 42),
    ("高端装维", "龙家宝", 42),
    ("高端装维", "罗紫杰", 42),
    ("高端装维", "莫健铭", 42),
    ("高端装维", "吴广仁", 42),
    ("高端装维", "王洪明", 25),
]

# 区县目标（图4）：区县短名 → 目标（模板 P35:Q43）
COUNTY_TARGETS = [
    ("端州", 4.25), ("高要", 5.75), ("四会", 3.52), ("怀集", 3.97),
    ("德庆", 2.38), ("广宁", 2.60), ("封开", 2.41), ("鼎湖", 3.22),
    ("高新", 3.36),
]

# ── 字体 ──────────────────────────────────────────────────────────────
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
]


def _load_font(size, font_path=None):
    paths = [font_path] if font_path else []
    paths += _FONT_CANDIDATES
    for p in paths:
        if p and os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── 通用表格绘制 ──────────────────────────────────────────────────────
HEADER_BG = (47, 85, 151)
HEADER_FG = (255, 255, 255)
ROW_BG = (255, 255, 255)
ROW_ALT_BG = (242, 246, 252)
TOTAL_BG = (255, 244, 214)
BORDER = (200, 208, 220)
TEXT = (33, 37, 41)
TITLE = (20, 30, 55)


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        if v != v:           # NaN
            return ""
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{v:.2f}"
    return str(v)


def _fmt_pct(v):
    try:
        return f"{float(v) * 100:.1f}%"
    except (TypeError, ValueError):
        return ""


def render_table(title, headers, rows, out_png, font_path=None,
                 col_aligns=None, highlight_last=False):
    """
    通用表格图渲染。
        headers   : ["列1", "列2", ...]
        rows      : [[v, v, ...], ...]，每个元素已是字符串
        col_aligns: 每列对齐 "l"/"c"/"r"，缺省首列左对齐其余居中
    """
    n_cols = len(headers)
    if col_aligns is None:
        col_aligns = ["l"] + ["c"] * (n_cols - 1)

    f_title = _load_font(30, font_path)
    f_head = _load_font(20, font_path)
    f_cell = _load_font(19, font_path)

    pad_x, pad_y = 16, 11
    title_h = 56
    row_h = 40

    # 量算各列宽
    tmp = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(tmp)

    def text_w(txt, font):
        box = d.textbbox((0, 0), txt, font=font)
        return box[2] - box[0]

    col_w = []
    for c in range(n_cols):
        w = text_w(headers[c], f_head)
        for r in rows:
            w = max(w, text_w(r[c], f_cell))
        col_w.append(w + pad_x * 2)

    table_w = sum(col_w)
    table_h = title_h + row_h * (len(rows) + 1)
    margin = 24
    img_w = table_w + margin * 2
    img_h = table_h + margin * 2

    img = Image.new("RGB", (img_w, img_h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 标题
    tb = draw.textbbox((0, 0), title, font=f_title)
    draw.text((margin + (table_w - (tb[2] - tb[0])) / 2, margin + 8),
              title, fill=TITLE, font=f_title)

    x0, y0 = margin, margin + title_h

    def draw_row(y, cells, font, bg, fg):
        x = x0
        draw.rectangle([x0, y, x0 + table_w, y + row_h], fill=bg)
        for c in range(n_cols):
            cell = cells[c]
            cw = col_w[c]
            box = draw.textbbox((0, 0), cell, font=font)
            tw = box[2] - box[0]
            align = col_aligns[c]
            if align == "l":
                tx = x + pad_x
            elif align == "r":
                tx = x + cw - pad_x - tw
            else:
                tx = x + (cw - tw) / 2
            draw.text((tx, y + pad_y), cell, fill=fg, font=font)
            x += cw

    # 表头
    draw_row(y0, headers, f_head, HEADER_BG, HEADER_FG)
    # 数据行
    y = y0 + row_h
    for i, r in enumerate(rows):
        is_last = highlight_last and (i == len(rows) - 1)
        bg = TOTAL_BG if is_last else (ROW_ALT_BG if i % 2 else ROW_BG)
        draw_row(y, r, f_cell, bg, TEXT)
        y += row_h

    # 网格线
    gx = x0
    for c in range(n_cols + 1):
        draw.line([gx, y0, gx, y], fill=BORDER, width=1)
        if c < n_cols:
            gx += col_w[c]
    gy = y0
    for _ in range(len(rows) + 2):
        draw.line([x0, gy, x0 + table_w, gy], fill=BORDER, width=1)
        gy += row_h

    img.save(out_png)
    return out_png


# ── 从结果 Excel 各 sheet 取数（pandas，不依赖公式）────────────────────
def _read_sheet(path, sheet, header=0):
    return pd.read_excel(path, sheet_name=sheet, header=header)


def _series_map(df, key_col, val_col):
    m = {}
    for _, row in df.iterrows():
        k = str(row[key_col]).strip()
        try:
            m[k] = float(row[val_col])
        except (TypeError, ValueError):
            m[k] = 0.0
    return m


def _days_elapsed():
    """当月已过天数 = DAY(昨天)，与模板 U5=DAY(TODAY()-1) 一致。"""
    return (date.today() - timedelta(days=1)).day


def _read_coop_mapping(result_xlsx):
    """
    从结果 Excel 的「交付高装」sheet 读协同映射（J/K/M 列）。
    返回 list of (客户经理, 装维协同, 协同交付经理)，名称去除括号备注。
    若 sheet 不存在则返回 None（回退到按姓名直配）。
    """
    try:
        df = pd.read_excel(result_xlsx, sheet_name="交付高装", header=0)
    except Exception:
        return None
    cols = list(df.columns)
    if len(cols) < 13:
        return None
    j_col, k_col, m_col = cols[9], cols[10], cols[12]

    def clean(v):
        s = str(v).strip()
        if s in ("nan", "None", ""):
            return ""
        # 去掉括号及其后备注
        for sep in ("（", "("):
            if sep in s:
                s = s.split(sep)[0].strip()
        return s

    mapping = []
    for _, row in df.iterrows():
        j, k, m = clean(row[j_col]), clean(row[k_col]), clean(row[m_col])
        if not j and not k and not m:
            continue
        mapping.append((j, k, m))
    return mapping or None


# ── 图1：完美一单积分完成通报 ────────────────────────────────────────
def render_perfect_points(result_xlsx, out_png, font_path=None):
    df = _read_sheet(result_xlsx, "完美一单")  # 列：姓名/高套/积分完成/新增积分（全业务）
    points = _series_map(df, "姓名", "积分完成")

    headers = ["团队", "姓名", "积分目标", "积分完成", "完成率"]
    rows = []

    def add_group(group_label, members):
        sub_total_target = 0
        sub_total_done = 0.0
        for i, name in enumerate(members):
            done = points.get(name, 0.0)
            sub_total_target += PERFECT_POINT_TARGET
            sub_total_done += done
            rows.append([
                group_label if i == 0 else "",
                name,
                _fmt(PERFECT_POINT_TARGET),
                _fmt(done),
                _fmt_pct(done / PERFECT_POINT_TARGET) if PERFECT_POINT_TARGET else "",
            ])
        rows.append([
            f"{group_label}合计", "",
            _fmt(sub_total_target), _fmt(sub_total_done),
            _fmt_pct(sub_total_done / sub_total_target) if sub_total_target else "",
        ])

    add_group("党政军", TEAM_PARTY)
    add_group("大企业", TEAM_ENTERPRISE)

    grand_target = PERFECT_POINT_TARGET * (len(TEAM_PARTY) + len(TEAM_ENTERPRISE))
    grand_done = sum(points.get(n, 0.0) for n in TEAM_PARTY + TEAM_ENTERPRISE)
    rows.append([
        "合计", "",
        _fmt(grand_target), _fmt(grand_done),
        _fmt_pct(grand_done / grand_target) if grand_target else "",
    ])

    return render_table("完美一单积分完成通报", headers, rows, out_png,
                        font_path=font_path, highlight_last=True)


# ── 图2：高装高套目标完成情况 ────────────────────────────────────────
def render_gaozhuang(result_xlsx, out_png, font_path=None):
    df = _read_sheet(result_xlsx, "高装高套")  # 列：姓名/高套数/发展目标
    cols = list(df.columns)
    name_col = cols[0]
    val_col = cols[1] if len(cols) > 1 else cols[0]
    target_col = cols[2] if len(cols) > 2 else None

    headers = ["姓名", "高套数", "目标", "完成率"]
    rows = []
    total_val = 0.0
    total_target = 0.0
    for _, row in df.iterrows():
        name = str(row[name_col]).strip()
        if not name or name == "nan":
            continue
        try:
            val = float(row[val_col])
        except (TypeError, ValueError):
            val = 0.0
        try:
            tgt = float(row[target_col]) if target_col else 1.0
        except (TypeError, ValueError):
            tgt = 1.0
        total_val += val
        total_target += tgt
        rows.append([name, _fmt(val), _fmt(tgt),
                     _fmt_pct(val / tgt) if tgt else ""])

    rows.append(["合计", _fmt(total_val), _fmt(total_target),
                 _fmt_pct(total_val / total_target) if total_target else ""])

    return render_table("高装高套目标完成情况", headers, rows, out_png,
                        font_path=font_path, highlight_last=True)


# ── 图3：全光任务完成情况 ────────────────────────────────────────────
def _read_quanguang_roster(result_xlsx):
    """
    从「交付高装」sheet 读取图3名单：A=岗位角色, B=姓名, C=发展目标。
    返回 list of (岗位, 姓名, 目标)。失败返回 None（回退到内置 QUANGUANG_TARGETS）。
    """
    try:
        df = pd.read_excel(result_xlsx, sheet_name="交付高装", header=0)
    except Exception:
        return None
    cols = list(df.columns)
    if len(cols) < 3:
        return None
    role_col, name_col, target_col = cols[0], cols[1], cols[2]
    roster = []
    last_role = ""
    for _, row in df.iterrows():
        name = str(row[name_col]).strip()
        if not name or name == "nan":
            continue
        role = str(row[role_col]).strip()
        if role and role != "nan":
            last_role = role
        try:
            target = float(row[target_col])
        except (TypeError, ValueError):
            continue
        roster.append((last_role, name, target))
    return roster or None


def render_quanguang(result_xlsx, out_png, font_path=None):
    df = _read_sheet(result_xlsx, "全光组网")  # 列：姓名/主从网关数
    cols = list(df.columns)
    gw = _series_map(df, cols[0], cols[1])  # 客户经理 → 全光组网网关数

    # 协同映射：把客户经理的网关数按「交付高装」结对关系归集到本人名下
    coop = _read_coop_mapping(result_xlsx)
    done_by_person = {}
    if coop:
        # 高端装维：装维协同列匹配；智云工程师：协同交付经理列匹配
        for manager, weiwei, jiaofu in coop:
            val = gw.get(manager, 0.0)
            if weiwei:
                done_by_person[weiwei] = done_by_person.get(weiwei, 0.0) + val
            if jiaofu:
                done_by_person[jiaofu] = done_by_person.get(jiaofu, 0.0) + val

    # 名单与目标优先从「交付高装」sheet 读取，回退到内置常量
    roster = _read_quanguang_roster(result_xlsx) or QUANGUANG_TARGETS

    headers = ["岗位角色", "姓名", "发展目标", "主从网关数", "完成率"]
    rows = []
    total_done = 0.0
    total_target = 0.0
    for role, name, target in roster:
        # 优先用协同归集结果，无映射时回退按姓名直配
        done = done_by_person.get(name, gw.get(name, 0.0)) if coop else gw.get(name, 0.0)
        total_done += done
        total_target += target
        rows.append([role, name, _fmt(target), _fmt(done),
                     _fmt_pct(done / target) if target else ""])

    rows.append(["合计", "", _fmt(total_target), _fmt(total_done),
                 _fmt_pct(total_done / total_target) if total_target else ""])

    return render_table("全光任务完成情况", headers, rows, out_png,
                        font_path=font_path, highlight_last=True)


# ── 图4：区县目标完成情况 ────────────────────────────────────────────
def render_county(result_xlsx, out_png, font_path=None):
    df = _read_sheet(result_xlsx, "高套")  # 列：姓名/高套数（含区县短名行）
    cols = list(df.columns)
    gaotao = _series_map(df, cols[0], cols[1])

    # 模板：完成 = ROUND(高套数 / 当月已过天数, 2)，完成率 = 完成 / 目标（日均口径）
    days = _days_elapsed() or 1

    headers = ["区县", "目标", "完成", "完成率"]
    rows = []
    total_target = 0.0
    total_done = 0.0
    for county, target in COUNTY_TARGETS:
        raw = gaotao.get(county, 0.0)
        done = round(raw / days, 2)
        total_target += target
        total_done += done
        rows.append([county, _fmt(target), _fmt(done),
                     _fmt_pct(done / target) if target else ""])

    rows.append(["合计", _fmt(total_target), _fmt(round(total_done, 2)),
                 _fmt_pct(total_done / total_target) if total_target else ""])

    return render_table("区县目标完成情况", headers, rows, out_png,
                        font_path=font_path, highlight_last=True)


def render_all(result_xlsx, out_dir, font_path=None):
    """生成四张图，返回有序的 (标题, png路径) 列表。"""
    os.makedirs(out_dir, exist_ok=True)
    specs = [
        ("完美一单积分完成通报", render_perfect_points, "01_perfect_points.png"),
        ("高装高套目标完成情况", render_gaozhuang, "02_gaozhuang.png"),
        ("全光任务完成情况", render_quanguang, "03_quanguang.png"),
        ("区县目标完成情况", render_county, "04_county.png"),
    ]
    results = []
    for title, fn, fname in specs:
        png = os.path.join(out_dir, fname)
        fn(result_xlsx, png, font_path=font_path)
        results.append((title, png))
    return results
