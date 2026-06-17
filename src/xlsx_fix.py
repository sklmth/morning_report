"""
导图前的结果 Excel 预处理：修复 LibreOffice 无法识别的函数前缀，并（可选）
让 LibreOffice 重算后把公式固化为数值。

背景：openpyxl/Excel 会把较新函数写成带 `_xlfn.` 前缀的形式，例如
`_xlfn.XLOOKUP(...)`。Microsoft Excel 能识别，但部分 LibreOffice 版本
（如 24.2 的某些路径）对该前缀求值会得到 `#NAME?`。把前缀去掉为
`XLOOKUP(...)` 后，LibreOffice 即可正常求值。

本模块只做字符串层面的安全替换，不改变公式语义。
"""

import re

import openpyxl

# 需要去掉 _xlfn. 前缀的函数（LibreOffice 原生支持其去前缀名）
_XLFN_FUNCS = [
    "XLOOKUP", "IFS", "SWITCH", "TEXTJOIN", "CONCAT", "MAXIFS", "MINIFS",
    "XMATCH", "FILTER", "SORT", "UNIQUE", "SEQUENCE",
]
_XLFN_RE = re.compile(r"_xlfn\.(" + "|".join(_XLFN_FUNCS) + r")", re.IGNORECASE)


def fix_xlfn_in_formula(formula):
    """把 `_xlfn.XLOOKUP` 等替换为 `XLOOKUP`。非字符串原样返回。"""
    if not isinstance(formula, str):
        return formula
    return _XLFN_RE.sub(r"\1", formula)


def fix_workbook_formulas(xlsx_path):
    """
    就地修复整个工作簿所有公式里的 `_xlfn.` 前缀。
    返回修复的公式单元格数量。
    """
    wb = openpyxl.load_workbook(xlsx_path)
    fixed = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                # 普通公式
                if isinstance(v, str) and v.startswith("=") and "_xlfn." in v:
                    cell.value = fix_xlfn_in_formula(v)
                    fixed += 1
                # 数组公式对象
                elif hasattr(v, "text") and isinstance(getattr(v, "text", None), str) \
                        and "_xlfn." in v.text:
                    try:
                        v.text = fix_xlfn_in_formula(v.text)
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
