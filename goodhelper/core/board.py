"""看板：一眼看清今天有什么、欠着什么。"""

from __future__ import annotations

from datetime import datetime, timedelta

from goodhelper.core.clock import fmt_short, humanize_delta
from goodhelper.core.config import Config
from goodhelper.core.store import Store


def _due_hint(due_at: str | None, now: datetime) -> str:
    if not due_at:
        return ""
    due = datetime.fromisoformat(due_at)
    delta = humanize_delta(due, now)
    return f"已过期，{delta}" if due < now else delta


def snapshot(store: Store, config: Config, now: datetime | None = None) -> dict:
    now = (now or datetime.now()).replace(second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59)
    tomorrow_end = today_end + timedelta(days=1)

    events_today = [
        {
            "id": row["id"],
            "title": row["title"],
            "start_at": row["start_at"],
            "when": fmt_short(datetime.fromisoformat(row["start_at"]), now),
        }
        for row in store.query(
            "SELECT id, title, start_at FROM events WHERE cancelled = 0 AND start_at >= ? "
            "AND start_at <= ? ORDER BY start_at",
            (now.isoformat(timespec="minutes"), today_end.isoformat(timespec="minutes")),
        )
    ]
    events_tomorrow = [
        {
            "id": row["id"],
            "title": row["title"],
            "start_at": row["start_at"],
            "when": fmt_short(datetime.fromisoformat(row["start_at"]), now),
        }
        for row in store.query(
            "SELECT id, title, start_at FROM events WHERE cancelled = 0 AND start_at > ? "
            "AND start_at <= ? ORDER BY start_at",
            (today_end.isoformat(timespec="minutes"), tomorrow_end.isoformat(timespec="minutes")),
        )
    ]
    todos = [
        {
            "id": row["id"],
            "content": row["content"],
            "due_at": row["due_at"],
            "priority": row["priority"],
            "due_hint": _due_hint(row["due_at"], now),
        }
        for row in store.query(
            "SELECT id, content, due_at, priority FROM todos WHERE done = 0 "
            "ORDER BY priority DESC, COALESCE(due_at, '9999') ASC LIMIT 10"
        )
    ]
    stats = {
        "notes": store.scalar("SELECT COUNT(*) FROM notes WHERE deleted = 0"),
        "todos_open": store.scalar("SELECT COUNT(*) FROM todos WHERE done = 0"),
        "todos_done": store.scalar("SELECT COUNT(*) FROM todos WHERE done = 1"),
        "events_today": len(events_today),
    }
    return {
        "now": now,
        "today": events_today,
        "tomorrow": events_tomorrow,
        "todos": todos,
        "stats": stats,
    }


def render(snapshot_data: dict, user_name: str = "朋友") -> str:
    now: datetime = snapshot_data["now"]
    hour = now.hour
    greet = "早上好" if 5 <= hour < 11 else "下午好" if 11 <= hour < 18 else "晚上好"
    lines = [f"{greet}，{user_name}。现在是 {now.strftime('%m-%d %H:%M')}。"]

    today = snapshot_data["today"]
    lines.append("")
    if today:
        lines.append("今天：")
        lines.extend(f"  · {item['when'].split(' ', 1)[-1]} {item['title']}" for item in today)
    else:
        lines.append("今天没有固定安排。")

    tomorrow = snapshot_data["tomorrow"]
    if tomorrow:
        lines.append("")
        lines.append("明天：")
        lines.extend(f"  · {item['when'].split(' ', 1)[-1]} {item['title']}" for item in tomorrow)

    todos = snapshot_data["todos"]
    lines.append("")
    if todos:
        lines.append(f"待办（{len(todos)} 条待清）：")
        for item in todos:
            mark = "!" if item["priority"] > 1 else "·"
            due = f"（{item['due_hint']}）" if item["due_hint"] else ""
            lines.append(f"  {mark} #{item['id']} {item['content']}{due}")
    else:
        lines.append("待办是空的。")

    stats = snapshot_data["stats"]
    lines.append("")
    lines.append(
        f"累计：备忘 {stats['notes']} 条 · 已完成 {stats['todos_done']} 条"
    )
    return "\n".join(lines)
