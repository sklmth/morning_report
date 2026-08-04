"""
天命赦令 - Flask API
提供休假管理、抽奖、统计接口
"""

from flask import Flask, request, jsonify, send_from_directory
from datetime import date, datetime
import os
import sys
from pathlib import Path

# 添加父目录到路径以访问主系统数据库
sys.path.insert(0, str(Path(__file__).parent.parent))

from tianming_decree import db, lottery
from wecom_notice.config import CUSTOMER_MANAGERS
from wecom_notice.db import get_fill_statistics

app = Flask(__name__, static_folder="static")

# 初始化数据库
db.init_tables()


@app.route("/")
def index():
    """前端页面"""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/managers", methods=["GET"])
def get_managers():
    """获取所有客户经理列表"""
    managers = [m["name"] for m in CUSTOMER_MANAGERS if not m.get("exclude_reminder", False)]
    return jsonify({"managers": managers})


@app.route("/api/vacation", methods=["POST"])
def add_vacation():
    """添加休假记录"""
    data = request.json
    manager_name = data.get("manager_name")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    note = data.get("note", "")

    if not all([manager_name, start_date, end_date]):
        return jsonify({"error": "缺少必填字段"}), 400

    vacation_id = db.add_vacation(manager_name, start_date, end_date, note)
    return jsonify({"success": True, "vacation_id": vacation_id})


@app.route("/api/vacation/<int:vacation_id>", methods=["DELETE"])
def delete_vacation(vacation_id):
    """删除休假记录"""
    success = db.delete_vacation(vacation_id)
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "记录不存在"}), 404


@app.route("/api/vacation", methods=["GET"])
def get_vacations():
    """获取休假记录列表"""
    manager_name = request.args.get("manager_name")
    vacations = db.get_vacations(manager_name)
    return jsonify({"vacations": vacations})


@app.route("/api/lottery/stats", methods=["GET"])
def get_lottery_stats():
    """获取当月所有客户经理的抽奖统计"""
    current_month = date.today().strftime("%Y-%m")

    # 从主系统同步准时次数
    sync_ontime_counts(current_month)

    # 获取所有统计
    stats = db.get_all_managers_stats(current_month)

    return jsonify({
        "month": current_month,
        "stats": stats
    })


@app.route("/api/lottery/my-stats", methods=["GET"])
def get_my_stats():
    """获取指定客户经理的详细统计"""
    manager_name = request.args.get("manager_name")
    if not manager_name:
        return jsonify({"error": "缺少 manager_name 参数"}), 400

    current_month = date.today().strftime("%Y-%m")

    # 同步准时次数
    sync_ontime_counts(current_month)

    # 获取月度统计
    stats = db.get_monthly_stats(manager_name, current_month)

    # 计算可用次数
    available_ontime = stats["ontime_count"] - stats["used_ontime_count"]
    available_lottery = available_ontime // 3

    # 获取可选消耗选项
    consume_options = lottery.get_available_consume_options(available_ontime)

    # 获取抽奖历史
    history = db.get_lottery_history(manager_name, current_month)

    return jsonify({
        "manager_name": manager_name,
        "month": current_month,
        "ontime_count": stats["ontime_count"],
        "used_ontime_count": stats["used_ontime_count"],
        "available_ontime": available_ontime,
        "available_lottery": available_lottery,
        "total_prize_amount": stats["total_prize_amount"],
        "consume_options": consume_options,
        "history": history
    })


@app.route("/api/lottery/probabilities", methods=["GET"])
def get_probabilities():
    """获取指定消耗次数下的中奖概率"""
    consumed_count = request.args.get("consumed_count", type=int, default=3)

    if consumed_count < 3:
        return jsonify({"error": "最少消耗3次准时记录"}), 400

    probabilities = lottery.get_prize_probabilities(consumed_count)
    return jsonify({"consumed_count": consumed_count, "probabilities": probabilities})


@app.route("/api/lottery/draw", methods=["POST"])
def perform_draw():
    """执行抽奖"""
    data = request.json
    manager_name = data.get("manager_name")
    consumed_count = data.get("consumed_count", 3)

    if not manager_name:
        return jsonify({"error": "缺少 manager_name"}), 400

    if consumed_count < 3:
        return jsonify({"error": "最少消耗3次准时记录"}), 400

    current_month = date.today().strftime("%Y-%m")

    # 同步并检查可用次数
    sync_ontime_counts(current_month)
    stats = db.get_monthly_stats(manager_name, current_month)
    available_ontime = stats["ontime_count"] - stats["used_ontime_count"]

    if available_ontime < consumed_count:
        return jsonify({"error": f"准时次数不足，当前可用 {available_ontime} 次"}), 400

    # 执行抽奖
    prize = lottery.draw_prize(consumed_count)

    # 记录抽奖历史
    db.add_lottery_record(manager_name, consumed_count, prize["name"], prize["amount"], current_month)

    # 更新统计
    db.consume_ontime_and_add_prize(manager_name, current_month, consumed_count, prize["amount"])

    return jsonify({
        "success": True,
        "prize": {
            "name": prize["name"],
            "amount": prize["amount"]
        },
        "consumed_count": consumed_count,
        "remaining_ontime": available_ontime - consumed_count
    })


@app.route("/api/lottery/history", methods=["GET"])
def get_history():
    """获取抽奖历史"""
    manager_name = request.args.get("manager_name")
    month = request.args.get("month")

    history = db.get_lottery_history(manager_name, month)
    return jsonify({"history": history})


def sync_ontime_counts(month: str):
    """
    从主系统 fill_statistics 表同步当月准时次数。
    只统计 fill_status = 'on_time' 的记录。
    """
    # 获取月份范围
    year, mon = map(int, month.split("-"))
    start_date = f"{year}-{mon:02d}-01"

    # 计算月末
    if mon == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{mon + 1:02d}-01"

    # 从主系统查询准时记录
    all_stats = get_fill_statistics(start_date=start_date, end_date=end_date)

    # 统计每人的准时次数
    ontime_counts = {}
    for stat in all_stats:
        if stat["fill_status"] == "on_time":
            mgr = stat["manager_name"]
            ontime_counts[mgr] = ontime_counts.get(mgr, 0) + 1

    # 更新到月度统计表
    for mgr, count in ontime_counts.items():
        db.update_monthly_stats(mgr, month, count)


if __name__ == "__main__":
    host = os.environ.get("TIANMING_HOST", "127.0.0.1")
    port = int(os.environ.get("TIANMING_PORT", "8888"))
    debug = os.environ.get("TIANMING_DEBUG", "0") in {"1", "true", "True", "yes"}
    print("天命赦令系统启动中...")
    print(f"服务地址: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
