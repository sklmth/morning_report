"""营服报表 —— 客户经理新增/存量高套清单模块。

对外主接口：
    from gaotao_stats import process_excel
    df_new, df_stock, out_path = process_excel("营服报表.xlsx", "输出.xlsx")

列映射与口径见 processor.py。
"""

from .processor import (  # noqa: F401
    process_excel, compute_tables, NAMES,
)

__all__ = ["process_excel", "compute_tables", "NAMES"]
