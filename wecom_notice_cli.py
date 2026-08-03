#!/usr/bin/env python
"""企业微信通知系统 - 快速启动和管理工具"""

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))


def start_server(port=8996, enable_scheduler=False):
    """启动服务"""
    import os
    import uvicorn

    print(f"启动企业微信通知服务...")
    print(f"端口: {port}")
    print(f"调度器: {'已启用' if enable_scheduler else '未启用（需要手动启动）'}")
    print(f"API文档: http://127.0.0.1:{port}/docs")
    print()

    os.environ["WECOM_NOTICE_PORT"] = str(port)

    uvicorn.run(
        "wecom_notice.api:app",
        host="127.0.0.1",
        port=port,
        reload=False,
    )


def test_system():
    """测试系统功能"""
    from wecom_notice.config import CUSTOMER_MANAGERS, GAOZHUANG_STAFF, ZHIYUN_ENGINEERS, MANAGER_RECIPIENTS
    from wecom_notice.db import init_db, get_records
    from wecom_notice.reporter import build_cumulative_statistics

    print("=" * 60)
    print("企业微信通知系统 - 功能测试")
    print("=" * 60)
    print()

    # 配置测试
    print("[1/4] 配置加载...")
    print(f"  客户经理: {len(CUSTOMER_MANAGERS)} 人")
    print(f"  高端装维: {len(GAOZHUANG_STAFF)} 人")
    print(f"  智云工程师: {len(ZHIYUN_ENGINEERS)} 人")
    print(f"  管理者: {len(MANAGER_RECIPIENTS)} 人")
    print()

    # 数据库测试
    print("[2/4] 数据库初始化...")
    init_db()
    records = get_records(limit=5)
    print(f"  预约记录: {len(records)} 条")
    print()

    # 统计测试
    print("[3/4] 累计统计...")
    stats = build_cumulative_statistics()
    print(f"  准时填报: {len(stats['on_time'])} 人")
    print(f"  超时填报: {len(stats['overtime'])} 人")
    print(f"  漏填情况: {len(stats['missing'])} 人")
    print()

    # Excel测试
    print("[4/4] Excel导出...")
    from wecom_notice.excel_export import export_cumulative_stats
    out_path = ROOT_DIR / "runtime" / "测试导出.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    export_cumulative_stats(stats, str(out_path), "测试")
    print(f"  文件: {out_path}")
    print(f"  大小: {out_path.stat().st_size} 字节")
    print()

    print("=" * 60)
    print("所有测试通过！")
    print("=" * 60)


def export_stats(start_date="", end_date="", output=""):
    """导出累计统计"""
    from datetime import date, timedelta
    from wecom_notice.reporter import build_cumulative_statistics
    from wecom_notice.excel_export import export_cumulative_stats

    if not end_date:
        end_date = date.today().isoformat()
    if not start_date:
        start_date = (date.today() - timedelta(days=30)).isoformat()
    if not output:
        output = f"runtime/累计统计_{start_date}至{end_date}.xlsx"

    print(f"生成累计统计...")
    print(f"  起始日期: {start_date}")
    print(f"  结束日期: {end_date}")

    stats = build_cumulative_statistics(start_date, end_date)
    date_range = f"{start_date}至{end_date}"

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    export_cumulative_stats(stats, str(out_path), date_range)

    print(f"  输出文件: {out_path}")
    print(f"  准时: {len(stats['on_time'])} 人")
    print(f"  超时: {len(stats['overtime'])} 人")
    print(f"  漏填: {len(stats['missing'])} 人")
    print(f"\n导出完成！")


def show_status():
    """显示系统状态"""
    import requests

    print("查询系统状态...")
    try:
        resp = requests.get("http://127.0.0.1:8996/api/scheduler/status", timeout=5)
        data = resp.json()

        print(f"\n调度器状态: {'运行中' if data['enabled'] else '未运行'}")
        if data['enabled']:
            print(f"定时任务数: {data['count']}")
            print("\n近期任务:")
            for job in data['jobs'][:5]:
                print(f"  - {job['name']}: {job['next_run_time']}")
        else:
            print("提示: 使用 --start-scheduler 启动调度器")

    except requests.exceptions.ConnectionError:
        print("\n[错误] 服务未运行")
        print("提示: 使用 python wecom_notice_cli.py start 启动服务")
    except Exception as e:
        print(f"\n[错误] {e}")


def main():
    parser = argparse.ArgumentParser(
        description="企业微信通知系统 - 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python wecom_notice_cli.py start                     # 启动服务
  python wecom_notice_cli.py start --enable-scheduler  # 启动服务并启用调度器
  python wecom_notice_cli.py test                      # 测试功能
  python wecom_notice_cli.py export                    # 导出最近30天统计
  python wecom_notice_cli.py export --start 2026-01-01 --end 2026-01-31
  python wecom_notice_cli.py status                    # 查看状态
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # start命令
    start_parser = subparsers.add_parser("start", help="启动服务")
    start_parser.add_argument("--port", type=int, default=8996, help="端口号（默认8996）")
    start_parser.add_argument("--enable-scheduler", action="store_true", help="启动时启用调度器")

    # test命令
    subparsers.add_parser("test", help="测试系统功能")

    # export命令
    export_parser = subparsers.add_parser("export", help="导出累计统计Excel")
    export_parser.add_argument("--start", dest="start_date", default="", help="起始日期 (YYYY-MM-DD)")
    export_parser.add_argument("--end", dest="end_date", default="", help="结束日期 (YYYY-MM-DD)")
    export_parser.add_argument("-o", "--output", default="", help="输出文件路径")

    # status命令
    subparsers.add_parser("status", help="查看系统状态")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "start":
        start_server(args.port, args.enable_scheduler)
    elif args.command == "test":
        test_system()
    elif args.command == "export":
        export_stats(args.start_date, args.end_date, args.output)
    elif args.command == "status":
        show_status()


if __name__ == "__main__":
    main()
