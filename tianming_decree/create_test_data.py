"""
创建天命赦令测试数据
为指定客户经理添加准时次数，用于测试抽签功能
"""

import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from tianming_decree import db
from datetime import date


def create_test_data():
    """创建测试数据"""

    # 初始化表
    db.init_tables()

    # 获取当前月份
    current_month = date.today().strftime("%Y-%m")

    # 测试用户列表
    test_users = [
        {"name": "黄家诚", "phone": "19902381680"},
        {"name": "曾俊宁", "phone": "18128089992"}
    ]
    test_ontime_count = 21  # 足够抽7次（消耗3-7次）

    conn = db.get_connection()
    cursor = conn.cursor()

    for test_user in test_users:
        test_manager = test_user["name"]

        print(f"\n正在为 {test_manager} ({test_user['phone']}) 创建测试数据...")
        print(f"月份: {current_month}")
        print(f"准时次数: {test_ontime_count}")

        # 先删除旧记录
        cursor.execute(
            "DELETE FROM monthly_lottery_stats WHERE manager_name = ? AND month = ?",
            (test_manager, current_month)
        )

        # 插入新记录
        cursor.execute(
            """
            INSERT INTO monthly_lottery_stats (manager_name, month, ontime_count, used_ontime_count, total_prize_amount)
            VALUES (?, ?, ?, 0, 0)
            """,
            (test_manager, current_month, test_ontime_count)
        )

        # 验证数据
        cursor.execute(
            "SELECT manager_name, month, ontime_count, used_ontime_count, total_prize_amount FROM monthly_lottery_stats WHERE manager_name = ? AND month = ?",
            (test_manager, current_month)
        )
        result = cursor.fetchone()
        if result:
            available = (result[2] - result[3]) // 3
            print(f"验证结果: 姓名={result[0]}, 月份={result[1]}, 准时次数={result[2]}, 已用次数={result[3]}")
            print(f"剩余可消耗次数: {available}")

    conn.commit()
    conn.close()

    print("\n测试数据创建完成!")
    print("现在可以使用以下用户测试抽签功能了:")
    for user in test_users:
        print(f"  - {user['name']} ({user['phone']})")
    print("访问地址: https://shanguantang.site/tianming/")


if __name__ == "__main__":
    create_test_data()
