#!/usr/bin/env python
"""企业微信通知系统功能测试脚本"""

import sys
from datetime import date, timedelta
from pathlib import Path

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

def test_config():
    """测试配置加载"""
    print("=" * 50)
    print("测试1: 配置加载")
    print("=" * 50)

    from wecom_notice.config import (
        CUSTOMER_MANAGERS,
        GAOZHUANG_STAFF,
        ZHIYUN_ENGINEERS,
        MANAGER_RECIPIENTS
    )

    print(f"[OK] 客户经理数量: {len(CUSTOMER_MANAGERS)}")
    print(f"[OK] 高端装维数量: {len(GAOZHUANG_STAFF)}")
    print(f"[OK] 智云工程师数量: {len(ZHIYUN_ENGINEERS)}")
    print(f"[OK] 管理者数量: {len(MANAGER_RECIPIENTS)}")
    print()


def test_database():
    """测试数据库功能"""
    print("=" * 50)
    print("测试2: 数据库功能")
    print("=" * 50)

    from wecom_notice.db import (
        init_db,
        get_records,
        get_fill_statistics,
        get_reminder_logs,
    )

    # 初始化数据库
    init_db()
    print("✓ 数据库初始化成功")

    # 查询记录
    records = get_records(limit=10)
    print(f"✓ 查询预约记录: {len(records)} 条")

    # 查询统计
    stats = get_fill_statistics()
    print(f"✓ 查询填报统计: {len(stats)} 条")

    # 查询提醒日志
    logs = get_reminder_logs(limit=10)
    print(f"✓ 查询提醒日志: {len(logs)} 条")
    print()


def test_reporter():
    """测试通报构建器"""
    print("=" * 50)
    print("测试3: 通报构建器")
    print("=" * 50)

    from wecom_notice.reporter import (
        build_customer_manager_reminder,
        build_manager_brief_notice,
        build_manager_detailed_notice,
        build_final_data_collection,
        build_cumulative_statistics,
    )

    target_date = (date.today() + timedelta(days=1)).isoformat()

    # 测试客户经理提醒
    try:
        report = build_customer_manager_reminder(target_date, "麦海芬")
        print(f"✓ 客户经理提醒: should_send={report.get('should_send', False)}")
    except Exception as e:
        print(f"✗ 客户经理提醒失败: {e}")

    # 测试管理者简洁通报
    try:
        report = build_manager_brief_notice(target_date)
        print(f"✓ 管理者简洁通报: should_send={report.get('should_send', False)}")
    except Exception as e:
        print(f"✗ 管理者简洁通报失败: {e}")

    # 测试管理者详细通报
    try:
        report = build_manager_detailed_notice(target_date)
        print(f"✓ 管理者详细通报: should_send={report.get('should_send', False)}")
    except Exception as e:
        print(f"✗ 管理者详细通报失败: {e}")

    # 测试最终数据收集
    try:
        report = build_final_data_collection(target_date)
        print(f"✓ 最终数据收集: {len(report.get('results', []))} 位客户经理")
    except Exception as e:
        print(f"✗ 最终数据收集失败: {e}")

    # 测试累计统计
    try:
        stats = build_cumulative_statistics()
        print(f"✓ 累计统计: 准时{len(stats['on_time'])} 超时{len(stats['overtime'])} 漏填{len(stats['missing'])}")
    except Exception as e:
        print(f"✗ 累计统计失败: {e}")

    print()


def test_excel_export():
    """测试Excel导出"""
    print("=" * 50)
    print("测试4: Excel导出功能")
    print("=" * 50)

    from wecom_notice.reporter import build_cumulative_statistics
    from wecom_notice.excel_export import export_cumulative_stats

    try:
        stats = build_cumulative_statistics()
        out_path = ROOT_DIR / "runtime" / "test_stats.xlsx"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        export_cumulative_stats(stats, str(out_path), "测试数据")

        if out_path.exists():
            print(f"✓ Excel导出成功: {out_path}")
            print(f"  文件大小: {out_path.stat().st_size} 字节")
        else:
            print("✗ Excel文件未生成")
    except Exception as e:
        print(f"✗ Excel导出失败: {e}")

    print()


def test_api_imports():
    """测试API模块导入"""
    print("=" * 50)
    print("测试5: API模块导入")
    print("=" * 50)

    try:
        from wecom_notice.api import app
        print("✓ API模块导入成功")

        # 列出所有路由
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        print(f"✓ 注册路由数量: {len(routes)}")
        print("  主要路由:")
        for route in sorted(routes)[:10]:
            print(f"    - {route}")
    except Exception as e:
        print(f"✗ API模块导入失败: {e}")

    print()


def main():
    print("\n" + "=" * 50)
    print("企业微信通知系统 - 功能测试")
    print("=" * 50 + "\n")

    try:
        test_config()
        test_database()
        test_reporter()
        test_excel_export()
        test_api_imports()

        print("=" * 50)
        print("✓ 所有测试完成")
        print("=" * 50)
        print("\n提示:")
        print("1. 如需启动服务: python wecom_notice/main.py")
        print("2. 如需安装APScheduler: pip install APScheduler>=3.10.0")
        print("3. 配置企业微信webhook: 设置环境变量 WECOM_NOTICE_WEBHOOK_URL")
        print()

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
