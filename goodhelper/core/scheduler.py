"""提醒调度：把到点且还没提醒过的日程/待办捞出来，交给你选的通知方式。

不依赖后台常驻进程：每次启动 CLI、每次打开 Web、或 `goodhelper remind --watch`
都会顺手结算一次。是否提醒过记在数据库里，重复结算也不会重复通知。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from goodhelper.core.clock import fmt_short
from goodhelper.core.config import Config
from goodhelper.core.store import Store


@dataclass
class Alert:
    kind: str  # event / todo
    id: int
    title: str
    when: datetime

    def as_line(self, now: datetime | None = None) -> str:
        return f"[{self.kind_label}] {fmt_short(self.when, now)} · {self.title}"

    @property
    def kind_label(self) -> str:
        return "日程" if self.kind == "event" else "待办"


def due_alerts(store: Store, config: Config, now: datetime | None = None) -> list[Alert]:
    """到点窗口内的未提醒项：时间落在 (现在 - 1 天, 现在 + 提前量]，且 notified_at 为空。"""
    now = (now or datetime.now()).replace(second=0, microsecond=0)
    lower = (now - timedelta(days=1)).isoformat(timespec="minutes")
    upper = (now + timedelta(minutes=max(config.remind_before, 0))).isoformat(timespec="minutes")
    alerts: list[Alert] = []

    for row in store.query(
        "SELECT id, title, start_at FROM events WHERE cancelled = 0 AND notified_at IS NULL "
        "AND start_at > ? AND start_at <= ?",
        (lower, upper),
    ):
        alerts.append(Alert("event", row["id"], row["title"], datetime.fromisoformat(row["start_at"])))

    for row in store.query(
        "SELECT id, content, due_at FROM todos WHERE done = 0 AND notified_at IS NULL "
        "AND due_at IS NOT NULL AND due_at > ? AND due_at <= ?",
        (lower, upper),
    ):
        alerts.append(Alert("todo", row["id"], row["content"], datetime.fromisoformat(row["due_at"])))

    return sorted(alerts, key=lambda alert: alert.when)


def acknowledge(store: Store, alerts: list[Alert], now: datetime | None = None) -> None:
    """把已经端到用户面前的提醒标记掉，下次不再重复。"""
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    for alert in alerts:
        table = "events" if alert.kind == "event" else "todos"
        store.execute(f"UPDATE {table} SET notified_at = ? WHERE id = ?", (stamp, alert.id))


def pending_within(store: Store, config: Config, now: datetime | None = None) -> list[Alert]:
    """取提醒并记账：调用方拿到 alerts 就视为已送达，不会重复打扰。"""
    alerts = due_alerts(store, config, now)
    if alerts:
        acknowledge(store, alerts, now)
    return alerts
