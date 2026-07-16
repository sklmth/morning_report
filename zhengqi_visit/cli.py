"""命令行入口：

    python -m zhengqi_visit.cli 输入.xlsx [输出.xlsx]
"""

import sys

from .processor import process_excel


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("用法: python -m zhengqi_visit.cli <输入.xlsx> [输出.xlsx]")
        return 1
    input_path = argv[0]
    out_path = argv[1] if len(argv) > 1 else None
    df, out = process_excel(input_path, out_path)
    print(f"已生成: {out}")
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
