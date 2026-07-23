"""命令行入口：

    python -m gaotao_stats.cli <营服报表.xlsx> [输出.xlsx]

从营服报表提取客户经理的新增高套（③高套清单）与存量高套（④存量高套清单），
生成含两 sheet 的 Excel，风格对齐「早会五张表」。
"""

import sys

from .processor import process_excel


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("用法: python -m gaotao_stats.cli <营服报表.xlsx> [输出.xlsx]")
        return 1
    input_path = argv[0]
    out_path = argv[1] if len(argv) > 1 else None
    df_new, df_stock, out = process_excel(input_path, out_path)
    print(f"已生成: {out}")
    print(f"  新增高套: {len(df_new)} 户，高套数合计 {df_new['高套数'].sum():g}")
    print(f"  存量高套: {len(df_stock)} 户，高套数合计 {df_stock['高套数'].sum():g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
