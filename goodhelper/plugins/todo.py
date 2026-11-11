"""待办：带优先级和截止时间的清单，支持完成、顺延与一次清空。"""

from __future__ import annotations

import re
from datetime import datetime

from goodhelper.core.clock import fmt_short, humanize_delta, parse_time
from goodhelper.core.plugin import Context, Reply, Rule, SimplePlugin

URGENT_RE = re.compile(r"紧急|马上|立刻|!{2,}|！！")
PRIORITY_MAP = {0: "低", 1: "普通", 2: "高"}


def _clean(title: str) -> str:
    return re.sub(r"^(?:请|那就|就)\s*", "", title).strip(" ，,。！!")


def _add(ctx: Context, match: re.Match[str]) -> Reply:
    raw = match.group("content") or ""
    parsed = parse_time(raw)
    due = parsed.when if parsed else None
    title = _clean(parsed.rest if parsed else raw)
    if not title:
        title = raw.strip()
    priority = 2 if URGENT_RE.search(title) else 1
    title = URGENT_RE.sub("", title).strip(" ，,。！!")
    if not title:
        return Reply("待办的内容是什么呢？", "todo.add.empty")
    todo_id = ctx.store.execute(
        "INSERT INTO todos(content, due_at, priority, created_at) VALUES(?, ?, ?, ?)",
        (title, due.isoformat(timespec="minutes") if due else None, priority, datetime.now().isoformat(timespec="seconds")),
    )
    when = f"，截止 {fmt_short(due)}" if due else ""
    return Reply(f"加好了 #{todo_id}：{title}{when}", "todo.add", {"id": todo_id})


def _list(ctx: Context, match: re.Match[str]) -> Reply:
    rows = ctx.store.query(
        "SELECT id, content, due_at, priority FROM todos WHERE done = 0 "
        "ORDER BY priority DESC, COALESCE(due_at, '9999') ASC, id ASC LIMIT 30"
    )
    if not rows:
        return Reply("待办清空了，难得。", "todo.list")
    now = datetime.now()
    lines = []
    for row in rows:
        due = datetime.fromisoformat(row["due_at"]) if row["due_at"] else None
        mark = "[" + PRIORITY_MAP[row["priority"]] + "] " if row["priority"] != 1 else ""
        hint = f" · ⏰ {fmt_short(due, now)}（{humanize_delta(due, now)}）" if due else ""
        lines.append(f"#{row['id']} {mark}{row['content']}{hint}")
    return Reply(f"待办 {len(rows)} 条：\n" + "\n".join(lines), "todo.list", {"count": len(rows)})


def _done(ctx: Context, match: re.Match[str]) -> Reply:
    raw = match.group("target") or ""
    num = re.search(r"\d+", raw)
    if num:
        todo_id = int(num.group(0))
        row = ctx.store.one("SELECT id, content FROM todos WHERE id = ? AND done = 0", (todo_id,))
        if row is None:
            return Reply(f"没有 #{todo_id} 这条未完成的待办。", "todo.done.missing")
        mark_done(ctx, todo_id)
        return Reply(f"完成 #{todo_id}：{row['content']}。", "todo.done", {"id": todo_id})

    keyword = raw.strip(" ，,。")
    rows = ctx.store.query(
        "SELECT id, content FROM todos WHERE done = 0 AND content LIKE ? ORDER BY id LIMIT 2",
        (f"%{keyword}%",),
    ) if keyword else []
    if len(rows) == 1:
        mark_done(ctx, rows[0]["id"])
        return Reply(f"完成 #{rows[0]['id']}：{rows[0]['content']}。", "todo.done", {"id": rows[0]["id"]})
    if len(rows) > 1:
        body = "\n".join(f"#{r['id']} {r['content']}" for r in rows)
        return Reply(f"「{keyword}」对上不止一条，说编号更准：\n{body}", "todo.done.ambiguous")
    return Reply("没找到要完成的待办。看看「待办」列表？", "todo.done.missing")


def mark_done(ctx: Context, todo_id: int) -> None:
    ctx.store.execute(
        "UPDATE todos SET done = 1, done_at = ? WHERE id = ?",
        (datetime.now().isoformat(timespec="seconds"), todo_id),
    )


def _clear_done(ctx: Context, match: re.Match[str]) -> Reply:
    count = ctx.store.scalar("SELECT COUNT(*) FROM todos WHERE done = 1")
    ctx.store.execute("DELETE FROM todos WHERE done = 1")
    return Reply(f"清掉了 {count} 条已完成的待办。", "todo.clean", {"count": count})


def _postpone(ctx: Context, match: re.Match[str]) -> Reply:
    todo_id = int(match.group("id"))
    row = ctx.store.one("SELECT id, content FROM todos WHERE id = ? AND done = 0", (todo_id,))
    if row is None:
        return Reply(f"没有 #{todo_id} 这条未完成的待办。", "todo.postpone.missing")
    duration = re.search(r"\d+", match.group("duration") or "")
    days = int(duration.group(0)) if duration else 1
    from datetime import timedelta

    base_row = ctx.store.one("SELECT due_at FROM todos WHERE id = ?", (todo_id,))
    base = datetime.fromisoformat(base_row["due_at"]) if base_row and base_row["due_at"] else datetime.now()
    new_due = base + timedelta(days=days)
    ctx.store.execute("UPDATE todos SET due_at = ? WHERE id = ?", (new_due.isoformat(timespec="minutes"), todo_id))
    return Reply(f"#{todo_id} 顺延到 {fmt_short(new_due)}。", "todo.postpone", {"id": todo_id})


PLUGIN = SimplePlugin(
    name="todo",
    title="待办",
    help=["待办 明天下午三点 写周报 紧急", "待办列表", "完成 3", "顺延 3 两天", "清理已完成"],
    rules=[
        Rule("todo.clean", r"^(?:清理|清空|清掉)(?:已完成|完成的|已办)(?:的)?(?:待办)?$", _clear_done, priority=15),
        Rule("todo.postpone", r"^顺延\s*#?(?P<id>\d+)\s*(?P<duration>[一两二三四五六七八九十\d]+\s*[天日])?$", _postpone, priority=15),
        Rule("todo.done", r"^(?:完成|做完了?|搞定|done)\s*[:：]?\s*(?P<target>.+)$", _done, priority=20),
        Rule("todo.list", r"^(?:待办列表|待办|看?待办|todo|任务列表)$", _list, priority=20),
        Rule("todo.add", r"^(?:待办|todo)\s*[:：,，]?\s*(?P<content>.+)$", _add, priority=25),
    ],
)
