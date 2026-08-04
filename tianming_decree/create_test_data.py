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

    # 测试用户：给"测试"用户添加足够的准时次数
    test_manager = "测试"
    test_ontime_count = 21  # 足够抽7次（消耗3-7次）

    print(f"正在为 {test_manager} 创建测试数据...")
    print(f"月份: {current_month}")
    print(f"准时次数: {test_ontime_count}")

    # 直接使用 upsert 更新或插入
    conn = db.get_connection()
    cursor = conn.cursor()

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

    conn.commit()
    conn.close()

    # 验证数据
    updated_stats = db.get_monthly_stats(test_manager, current_month)
    print(f"\n验证结果: {updated_stats}")
    available = (updated_stats['ontime_count'] - updated_stats['used_ontime_count']) // 3
    print(f"可用抽签次数: {available}")

    print("\n测试数据创建完成!")
    print(f"现在可以使用 '{test_manager}' 用户测试抽签功能了。")
    print("访问地址: https://shanguantang.site/tianming/")


if __name__ == "__main__":
    create_test_data()
