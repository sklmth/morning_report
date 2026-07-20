"""政企标准化信息收集 —— 家庭专项走访统计模块。

对外主接口：
    from zhengqi_visit import process_excel
    df, out_path = process_excel("输入.xlsx", "输出.xlsx")

统计口径见 processor.py。
"""

from .processor import (  # noqa: F401
    process_excel, process_rows,
    compute_stats, compute_stats_from_rows,
    VISIT_TYPE,
)

__all__ = [
    "process_excel", "process_rows",
    "compute_stats", "compute_stats_from_rows",
    "VISIT_TYPE",
]
