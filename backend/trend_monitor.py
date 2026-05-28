import datetime
from typing import Dict, List, Optional


class TrendMonitor:
    """滑动窗口趋势检测：同类工单短时间激增时触发告警"""

    def __init__(self, window_minutes: int = 10, threshold: int = 5):
        self._records: List[tuple] = []  # [(timestamp, category), ...]
        self._alerts: List[dict] = []
        self.window_minutes = window_minutes
        self.threshold = threshold

    def record(self, category: str) -> Optional[dict]:
        now = datetime.datetime.utcnow()
        self._records.append((now, category))
        self._prune_expired(now)

        # 统计窗口内各分类数量
        counts: Dict[str, int] = {}
        for ts, cat in self._records:
            counts[cat] = counts.get(cat, 0) + 1

        # 检查是否触发告警
        if counts.get(category, 0) >= self.threshold:
            # 检查是否已有同分类活跃告警（去重）
            for alert in self._alerts:
                if alert["category"] == category:
                    alert["count"] = counts[category]
                    alert["triggered_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    return None  # 已有告警，仅更新计数

            alert = {
                "category": category,
                "count": counts[category],
                "window_minutes": self.window_minutes,
                "threshold": self.threshold,
                "triggered_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "message": (
                    f"过去 {self.window_minutes} 分钟内收到 {counts[category]} 条"
                    f"「{category}」工单，可能存在大面积故障，建议排查。"
                ),
            }
            self._alerts.append(alert)
            return alert
        return None

    def get_active_alerts(self) -> List[dict]:
        now = datetime.datetime.utcnow()
        self._prune_expired(now)
        return list(self._alerts)

    def _prune_expired(self, now: datetime.datetime):
        cutoff = now - datetime.timedelta(minutes=self.window_minutes)
        self._records = [(ts, cat) for ts, cat in self._records if ts >= cutoff]
        # 清除过期告警（对应分类在窗口内不再满足阈值）
        counts: Dict[str, int] = {}
        for ts, cat in self._records:
            counts[cat] = counts.get(cat, 0) + 1
        self._alerts = [a for a in self._alerts if counts.get(a["category"], 0) >= self.threshold]


# 全局单例
monitor = TrendMonitor(window_minutes=10, threshold=5)
