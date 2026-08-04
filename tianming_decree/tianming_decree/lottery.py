"""
天命赦令 - 抽奖核心逻辑
奖品配置、概率计算、抽奖算法
"""

import random
from typing import TypedDict


class Prize(TypedDict):
    """奖品定义"""
    name: str
    amount: int  # 减免金额（元）
    base_weight: float  # 基础权重


# 奖品配置（修仙玄幻主题）
PRIZES: list[Prize] = [
    # 低阶奖品（高概率）
    {"name": "凡尘符咒", "amount": 0, "base_weight": 45.0},  # 空奖
    {"name": "聚灵丹", "amount": 5, "base_weight": 20.0},
    {"name": "护身符", "amount": 10, "base_weight": 15.0},

    # 中阶奖品（中概率）
    {"name": "筑基丹", "amount": 15, "base_weight": 10.0},
    {"name": "天罡令", "amount": 20, "base_weight": 6.0},

    # 高阶奖品（低概率）
    {"name": "金丹圣果", "amount": 25, "base_weight": 3.0},
    {"name": "天命赦令", "amount": 30, "base_weight": 1.0},
]


def calculate_weights(consumed_ontime_count: int) -> list[float]:
    """
    根据消耗的准时次数计算各奖品的实际权重。
    消耗越多，高价值奖品权重越高。

    参数：
        consumed_ontime_count: 本次消耗的准时次数（3/4/5...）

    返回：
        与 PRIZES 对应的权重列表
    """
    boost_factor = 1.0 + (consumed_ontime_count - 3) * 0.35  # 3次=1.0, 4次=1.35, 5次=1.7

    weights = []
    for prize in PRIZES:
        if prize["amount"] == 0:
            # 空奖权重随消耗次数降低
            weight = prize["base_weight"] / boost_factor
        elif prize["amount"] >= 25:
            # 高价值奖品权重随消耗次数提升
            weight = prize["base_weight"] * (boost_factor ** 2)
        elif prize["amount"] >= 15:
            # 中价值奖品权重适度提升
            weight = prize["base_weight"] * boost_factor
        else:
            # 低价值奖品权重保持
            weight = prize["base_weight"]

        weights.append(weight)

    return weights


def draw_prize(consumed_ontime_count: int) -> Prize:
    """
    执行一次抽奖。

    参数：
        consumed_ontime_count: 本次消耗的准时次数

    返回：
        抽中的奖品
    """
    weights = calculate_weights(consumed_ontime_count)
    selected = random.choices(PRIZES, weights=weights, k=1)[0]
    return selected


def get_prize_probabilities(consumed_ontime_count: int) -> list[dict]:
    """
    获取当前消耗次数下各奖品的中奖概率（用于前端展示）。

    返回：
        [{"name": "...", "amount": ..., "probability": 0.xx}, ...]
    """
    weights = calculate_weights(consumed_ontime_count)
    total_weight = sum(weights)

    result = []
    for prize, weight in zip(PRIZES, weights):
        result.append({
            "name": prize["name"],
            "amount": prize["amount"],
            "probability": round(weight / total_weight, 4),
        })

    return result


def get_available_consume_options(available_ontime: int) -> list[int]:
    """
    获取可消耗的准时次数选项。

    参数：
        available_ontime: 当前可用的准时次数

    返回：
        可选的消耗次数列表，例如 [3, 4, 5]
    """
    options = []
    for count in range(3, 8):  # 最多消耗7次
        if available_ontime >= count:
            options.append(count)
    return options
