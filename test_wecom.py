#!/usr/bin/env python3
"""
企业微信通报测试脚本

用途：快速测试消息发送到测试群聊
使用：python test_wecom.py [--prod]
      默认使用测试模式，加 --prod 参数使用生产环境
"""
import os
import sys
from datetime import date, timedelta

# 设置测试模式环境变量（必须在导入config之前）
if "--prod" not in sys.argv:
    os.environ["WECOM_NOTICE_TEST_MODE"] = "true"
    print("🧪 测试模式已启用")
else:
    print("⚠️  生产模式已启用")

from wecom_notice.config import CUSTOMER_MANAGERS, TEST_PERSONNEL
from wecom_notice.db import get_records, get_rule, init_db
from wecom_notice.reporter import build_report
from wecom_notice.sender import send_text


def test_simple_message():
    """测试简单消息发送"""
    print("\n📤 测试1: 发送简单消息")

    recipients = TEST_PERSONNEL if "--prod" not in sys.argv else []
    message = "✅ 企业微信通报系统测试消息\n\n这是一条来自测试脚本的消息。"

    try:
        result = send_text(message, recipients)
        print(f"✅ 发送成功: {result}")
        return True
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        return False


def test_mention_users():
    """测试@提醒功能"""
    print("\n📤 测试2: @提醒测试")

    if "--prod" in sys.argv:
        print("⚠️  生产模式下跳过@提醒测试")
        return True

    recipients = TEST_PERSONNEL
    message = "📢 @提醒测试\n\n本消息将@群内相关人员。"

    try:
        result = send_text(message, recipients)
        print(f"✅ 发送成功: {result}")
        print(f"📱 @了以下人员:")
        for person in recipients:
            mobile = person.get("mobile", "无")
            print(f"   - {person['name']} ({person['title']}): {mobile}")
        return True
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        return False


def test_real_report():
    """测试真实通报数据"""
    print("\n📤 测试3: 真实通报数据测试")

    # 初始化数据库
    init_db()

    # 获取明天的日期
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    print(f"📅 查询日期: {tomorrow}")

    # 获取规则
    rule = get_rule("missing_tomorrow_booking")
    if not rule:
        print("❌ 未找到通报规则")
        return False

    # 构建通报
    report = build_report(tomorrow, rule)

    if not report.get("items"):
        print("✅ 所有客户经理已达标，无需通报")
        message = f"✅ 【{tomorrow} 预约情况】\n\n所有客户经理已完成明日预约（≥2户），无需提醒。"
    else:
        print(f"⚠️  发现 {len(report['items'])} 位客户经理未达标")
        message = report["message"]

    recipients = TEST_PERSONNEL if "--prod" not in sys.argv else report["recipients"]

    print(f"\n📝 消息内容预览:\n{'-'*50}\n{message}\n{'-'*50}")

    # 询问是否发送
    confirm = input("\n是否发送此消息? (y/n): ").lower()
    if confirm != 'y':
        print("❌ 已取消发送")
        return False

    try:
        result = send_text(message, recipients)
        print(f"✅ 发送成功: {result}")
        return True
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        return False


def main():
    print("=" * 60)
    print("🤖 企业微信通报系统 - 测试脚本")
    print("=" * 60)

    # 显示当前配置
    if "--prod" in sys.argv:
        print("\n⚠️  当前模式: 生产环境")
        print("📨 目标群聊: 正式企业微信群")
    else:
        print("\n🧪 当前模式: 测试环境")
        print("📨 目标群聊: 测试企业微信群")
        print("👥 测试人员:")
        for person in TEST_PERSONNEL:
            print(f"   - {person['name']} ({person['title']}): {person['mobile']}")

    print("\n" + "=" * 60)

    # 运行测试
    tests = [
        ("简单消息", test_simple_message),
        ("@提醒", test_mention_users),
        ("真实通报", test_real_report),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n{'='*60}")
        try:
            success = test_func()
            results.append((name, success))
        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断测试")
            break
        except Exception as e:
            print(f"\n❌ 测试异常: {e}")
            results.append((name, False))

    # 显示测试结果
    print(f"\n\n{'='*60}")
    print("📊 测试结果汇总")
    print("=" * 60)
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {name}")
    print("=" * 60)

    # 返回退出码
    all_passed = all(success for _, success in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 测试已中断")
        sys.exit(130)
