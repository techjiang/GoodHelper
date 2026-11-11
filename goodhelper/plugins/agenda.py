"""日程：把「明天下午三点开会」变成一条日程，并给出前后文。"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from goodhelper.core.clock import fmt_short, humanize_delta, parse_time
from goodhelper.core.plugin import Context, Reply, Rule, SimplePlugin

REMIND_PREFIX = re.compile(r"^(?:提醒我|记得|别忘了|到点提醒我)\s*")


def _add(ctx: Context, match: re.Match[str]) -> Reply:
    raw = (match.group("content") or "").strip()
    parsed = parse_time(raw)
    if parsed is None:
        return Reply(
            "我听出这是件有时有晌的事，但没抓住时间。换成「明天下午三点 开会」这种说法？",
            "agenda.add.no_time",
        )
    title = REMIND_PREFIX.sub("", parsed.rest).strip(" ，,。") or REMIND_PREFIX.sub("", raw).strip()
    event_id = ctx.store.execute(
        "INSERT INTO events(title, start_at, duration, created_at) VALUES(?, ?, 0, ?)",
        (title, parsed.when.isoformat(timespec="minutes"), datetime.now().isoformat(timespec="seconds")),
    )
    return Reply(
        f"排上了 #{event_id}：{fmt_short(parsed.when)}（{humanize_delta(parsed.when)}）{title}",
        "agenda.add",
        {"id": event_id, "start_at": parsed.when.isoformat(timespec="minutes")},
    )


def _list(ctx: Context, match: re.Match[str]) -> Reply:
    now = datetime.now()
    horizon = int(match.group("days")) if match.groupdict().get("days") else 7
    rows = ctx.store.query(
        "SELECT id, title, start_at FROM events WHERE cancelled = 0 AND start_at >= ? "
        "AND start_at <= ? ORDER BY start_at ASC",
        (now.isoformat(timespec="minutes"), (now + timedelta(days=horizon)).isoformat(timespec="minutes")),
    )
    if not rows:
        return Reply(f"接下来 {horizon} 天空着。", "agenda.list", {"count": 0})
    lines = []
    for row in rows:
        start = datetime.fromisoformat(row["start_at"])
        lines.append(f"#{row['id']} {fmt_short(start, now)} · {row['title']}")
    return Reply(f"接下来 {horizon} 天：\n" + "\n".join(lines), "agenda.list", {"count": len(rows)})


def _next(ctx: Context, match: re.Match[str]) -> Reply:
    row = ctx.store.one(
        "SELECT id, title, start_at FROM events WHERE cancelled = 0 AND start_at >= ? "
        "ORDER BY start_at ASC LIMIT 1",
        (datetime.now().isoformat(timespec="minutes"),),
    )
    if row is None:
        return Reply("接下来没有安排。", "agenda.next")
    start = datetime.fromisoformat(row["start_at"])
    return Reply(
        f"下一件事：{fmt_short(start)}（{humanize_delta(start)}）{row['title']}",
        "agenda.next",
        {"id": row["id"], "start_at": row["start_at"]},
    )


def _cancel(ctx: Context, match: re.Match[str]) -> Reply:
    event_id = int(match.group("id"))
    row = ctx.store.one("SELECT id, title FROM events WHERE id = ? AND cancelled = 0", (event_id,))
    if row is None:
        return Reply(f"没有 #{event_id} 这条日程。", "agenda.cancel.missing")
    ctx.store.execute("UPDATE events SET cancelled = 1 WHERE id = ?", (event_id,))
    return Reply(f"取消了 #{event_id}：{row['title']}", "agenda.cancel")


PLUGIN = SimplePlugin(
    name="agenda",
    title="日程",
    help=["明天下午三点 开会", "日程", "日程 3 天", "下一件事", "取消日程 2"],
    rules=[
        Rule("agenda.cancel", r"^取消(?:日程|安排)?\s*#?(?P<id>\d+)$", _cancel, priority=15),
        Rule("agenda.next", r"^(?:下一件事|接下来|下一个安排)$", _next, priority=15),
        Rule("agenda.remind", r"^(?:提醒我|记得|别忘了|到点提醒我)\s*(?P<content>.+)$", _add, priority=18),
        Rule("agenda.list", r"^(?:日程|安排|看日程|agenda)(?:\s*(?P<days>\d+)\s*天)?$", _list, priority=15),
        # 兜底规则：带时间表达的整句都当日程，但让位给明确的待办/速记指令
        Rule("agenda.add", r"^(?!\s*(?:待办|todo|记一下|备忘|提醒|知识库))\s*(?P<content>.*(?:明天|后天|今天|今晚|明晚|下周|周[一二三四五六日天]|上午|下午|中午|晚上|\d{1,2}[:：点]).*)$", _add, priority=50),
    ],
)
