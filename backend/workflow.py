"""工单生命周期状态机 + 积分计算"""

from typing import Dict, List, Optional, Tuple
import datetime

STATUS_NEW       = "待分配"
STATUS_PROGRESS  = "处理中"
STATUS_REVIEW    = "待审核"
STATUS_DONE      = "已完成"
STATUS_RATED     = "已评价"

ALL_STATUSES = [STATUS_NEW, STATUS_PROGRESS, STATUS_REVIEW, STATUS_DONE, STATUS_RATED]

# 合法状态转换
TRANSITIONS: Dict[str, List[str]] = {
    STATUS_NEW:      [STATUS_PROGRESS],
    STATUS_PROGRESS: [STATUS_REVIEW],
    STATUS_REVIEW:   [STATUS_DONE],
    STATUS_DONE:     [STATUS_RATED],
    STATUS_RATED:    [],  # 终态
}


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in TRANSITIONS.get(from_status, [])


def get_next_status(current: str) -> Optional[str]:
    chain = TRANSITIONS.get(current, [])
    return chain[0] if chain else None


def calculate_points(action: str, response_seconds: int, risk_level: str,
                     rating: Optional[int] = None, event_multiplier: int = 1) -> Tuple[int, str]:
    """计算操作获得的积分，返回 (points, reason)"""
    points = 0
    reasons = []

    if action == "assign":
        if response_seconds < 60:
            points += 10
            reasons.append("⚡ 闪电分配 +10")
        elif response_seconds < 300:
            points += 5
            reasons.append("快速响应 +5")
        else:
            points -= 5
            reasons.append("响应超时 -5")

    elif action == "review":
        points += 5
        reasons.append("审核通过 +5")

    elif action == "resolve":
        if risk_level == "紧急":
            points += 30
            reasons.append("🔥 紧急工单 +30")
        elif risk_level == "高":
            points += 15
            reasons.append("高优工单 +15")

        if response_seconds < 120:
            points += 10
            reasons.append("极速处理 +10")

    elif action == "rate":
        if rating is not None:
            if rating >= 5:
                points += 20
                reasons.append("⭐⭐⭐⭐⭐ 好评 +20")
            elif rating >= 4:
                points += 15
                reasons.append("⭐⭐⭐⭐ 好评 +15")
            elif rating >= 3:
                points += 5
                reasons.append("⭐⭐⭐ 中评 +5")
            elif rating >= 2:
                points += 2
                reasons.append("⭐⭐ 一般 +2")
            else:
                reasons.append("⭐ 差评（不扣分，继续加油）")
            # 差评不扣分 — 谁被评价谁得分，不惩罚

    points *= event_multiplier
    if event_multiplier > 1:
        reasons.append(f"🎪 事件加成 x{event_multiplier}")

    return points, " | ".join(reasons) if reasons else "无积分变动"


def get_status_progress(status: str) -> int:
    """返回进度百分比 (0-100)"""
    mapping = {
        STATUS_NEW: 0,
        STATUS_PROGRESS: 25,
        STATUS_REVIEW: 50,
        STATUS_DONE: 75,
        STATUS_RATED: 100,
    }
    return mapping.get(status, 0)


def calculate_stress(action: str, risk_level: str = "中", rating: int = 0) -> int:
    """计算压力变化值，返回 delta (-100 ~ +100)"""
    if action == "assign":
        if risk_level == "紧急": return 25
        if risk_level == "高": return 15
        return 10
    elif action == "done":
        return -5
    elif action == "rated":
        if rating >= 4: return -10
        if rating <= 2: return 15
        return 0
    return 0


def get_stress_persona_effect(persona_name: str, stress: int) -> dict:
    """返回高压力下的人设崩坏效果 {speed_mult, rating_penalty, meltdown}"""
    if stress >= 95:
        return {"speed_mult": 3.0, "rating_penalty": 2, "meltdown": True}
    if stress >= 80:
        return {"speed_mult": 1.8, "rating_penalty": 1, "meltdown": True}
    if stress >= 60:
        return {"speed_mult": 1.3, "rating_penalty": 1, "meltdown": False}
    return {"speed_mult": 1.0, "rating_penalty": 0, "meltdown": False}
