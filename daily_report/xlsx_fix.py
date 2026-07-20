"""
导图前的结果 Excel 预处理：修复 LibreOffice 不兼容的公式，并（可选）
让 LibreOffice 重算后把公式固化为数值。

背景：
- openpyxl/Excel 会把较新函数写成带 `_xlfn.` 前缀的形式，例如
  `_xlfn.XLOOKUP(...)`。
- 即使去掉 `_xlfn.`，LibreOffice 24.2 在这份模板上仍可能把 `XLOOKUP`
  识别成 `#NAME?`。

因此这里做两层修复：
1) 去掉 `_xlfn.` 前缀；
2) 把 `XLOOKUP` 改写成 `INDEX/MATCH`，以便 LibreOffice 也能正确计算。

本模块只做字符串层面的安全替换，不改变结果语义。
"""

import re

import openpyxl

# 需要去掉 _xlfn. 前缀的函数（LibreOffice 原生支持其去前缀名）
_XLFN_FUNCS = [
    "XLOOKUP", "IFS", "SWITCH", "TEXTJOIN", "CONCAT", "MAXIFS", "MINIFS",
    "XMATCH", "FILTER", "SORT", "UNIQUE", "SEQUENCE",
]
_XLFN_RE = re.compile(r"_xlfn\.(" + "|".join(_XLFN_FUNCS) + r")", re.IGNORECASE)


def _split_top_level_args(arg_text):
    """按顶层逗号分割函数参数，忽略嵌套括号内的逗号。"""
    args = []
    depth = 0
    start = 0
    for i, ch in enumerate(arg_text):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            args.append(arg_text[start:i].strip())
            start = i + 1
    tail = arg_text[start:].strip()
    if tail:
        args.append(tail)
    return args


def _rewrite_xlookup_once(formula):
    """把公式字符串中的首个 XLOOKUP(...) 改写为 IFERROR(INDEX(...,MATCH(...)),...)。"""
    lower = formula.lower()
    idx = lower.find('xlookup(')
    if idx < 0:
        return formula, False

    # 找到对应右括号
    start = idx + len('xlookup(')
    depth = 1
    end = start
    while end < len(formula):
        ch = formula[end]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                break
        end += 1
    if depth != 0:
        return formula, False

    inner = formula[start:end]
    args = _split_top_level_args(inner)
    if len(args) < 3:
        return formula, False

    lookup_value = args[0]
    lookup_array = args[1]
    return_array = args[2]
    if_not_found = args[3] if len(args) >= 4 else '""'

    replacement = (
        f"IFERROR(INDEX({return_array},MATCH({lookup_value},{lookup_array},0))"
        f",{if_not_found})"
    )
    return formula[:idx] + replacement + formula[end + 1:], True


def rewrite_xlookup_formula(formula):
    """把公式里的 XLOOKUP 改写成 INDEX/MATCH。支持嵌套公式。"""
    if not isinstance(formula, str):
        return formula
    changed = False
    while True:
        formula2, ok = _rewrite_xlookup_once(formula)
        if not ok:
            break
        formula = formula2
        changed = True
    return formula


def fix_xlfn_in_formula(formula):
    """先去 `_xlfn.` 前缀，再把 XLOOKUP 改写为 INDEX/MATCH。"""
    if not isinstance(formula, str):
        return formula
    formula = _XLFN_RE.sub(r"\1", formula)
    formula = rewrite_xlookup_formula(formula)
    return formula


def fix_workbook_formulas(xlsx_path):
    """
    就地修复整个工作簿所有公式里的 `_xlfn.` 前缀与 XLOOKUP。
    返回修复的公式单元格数量。
    """
    wb = openpyxl.load_workbook(xlsx_path)
    fixed = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                # 普通公式
                if isinstance(v, str) and v.startswith("="):
                    new_v = fix_xlfn_in_formula(v)
                    if new_v != v:
                        cell.value = new_v
                        fixed += 1
                # 数组公式对象
                elif hasattr(v, "text") and isinstance(getattr(v, "text", None), str):
                    try:
                        new_text = fix_xlfn_in_formula(v.text)
                        if new_text != v.text:
                            v.text = new_text
                            fixed += 1
                    except Exception:
                        pass
    if fixed:
        wb.save(xlsx_path)
    return fixed


if __name__ == "__main__":
    import glob
    import os
    files = sorted(glob.glob(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "runtime", "output", "*.xlsx")))
    if files:
        n = fix_workbook_formulas(files[-1])
        print(f"修复 {n} 个公式：{files[-1]}")
    else:
        print("无结果 Excel")
