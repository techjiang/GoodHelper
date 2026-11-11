"""速记：一闪而过的想法先存下来，回头能搜到。"""

from __future__ import annotations

import re
from datetime import datetime

from goodhelper.core.plugin import Context, Reply, Rule, SimplePlugin

TAG_RE = re.compile(r"#(?P<tag>[\w\u4e00-\u9fa5]+)")
MEMO_PREFIX = re.compile(r"^(?:记一?下|记个|帮我记|备忘|速记|note|/memo)\s*[:：,，]?\s*", re.IGNORECASE)


def _add(ctx: Context, match: re.Match[str]) -> Reply:
    raw = match.group("content") or ""
    tags = TAG_RE.findall(raw)
    content = TAG_RE.sub("", raw).strip(" ，,。")
    if not content:
        return Reply("想记什么？把内容跟在「记一下」后面就行。", "note.add.empty")
    note_id = ctx.store.execute(
        "INSERT INTO notes(content, tags, created_at) VALUES(?, ?, ?)",
        (content, ",".join(tags), datetime.now().isoformat(timespec="seconds")),
    )
    tail = f"（标签：{'、'.join(tags)}）" if tags else ""
    return Reply(f"记好了 #{note_id}：{content}{tail}", "note.add", {"id": note_id})


def _list(ctx: Context, match: re.Match[str]) -> Reply:
    limit = 10
    rows = ctx.store.query(
        "SELECT id, content, tags, created_at FROM notes WHERE deleted = 0 ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    if not rows:
        return Reply("备忘本是空的。说「记一下 想买咖啡豆」试试。", "note.list")
    lines = []
    for row in rows:
        tags = f"  #{' #'.join(row['tags'].split(','))}" if row["tags"] else ""
        lines.append(f"#{row['id']} {row['content']}{tags}")
    return Reply("最近的备忘：\n" + "\n".join(lines), "note.list", {"count": len(rows)})


def _search(ctx: Context, match: re.Match[str]) -> Reply:
    keyword = (match.group("keyword") or "").strip()
    if not keyword:
        return Reply("搜什么关键词？", "note.search.empty")
    rows = ctx.store.query(
        "SELECT id, content, created_at FROM notes WHERE deleted = 0 AND content LIKE ? "
        "ORDER BY id DESC LIMIT 10",
        (f"%{keyword}%",),
    )
    if not rows:
        return Reply(f"没找到含有「{keyword}」的备忘。", "note.search")
    body = "\n".join(f"#{r['id']} {r['content']}" for r in rows)
    return Reply(f"找到 {len(rows)} 条：\n{body}", "note.search")


def _delete(ctx: Context, match: re.Match[str]) -> Reply:
    try:
        note_id = int(match.group("id"))
    except (TypeError, ValueError):
        return Reply("要删哪条？给我编号，比如「删掉备忘 3」。", "note.delete.empty")
    row = ctx.store.one("SELECT id, content FROM notes WHERE id = ? AND deleted = 0", (note_id,))
    if row is None:
        return Reply(f"没有 #{note_id} 这条备忘。", "note.delete.missing")
    ctx.store.execute("UPDATE notes SET deleted = 1 WHERE id = ?", (note_id,))
    return Reply(f"删掉了 #{note_id}：{row['content']}", "note.delete")


PLUGIN = SimplePlugin(
    name="note",
    title="速记",
    help=["记一下 想买咖啡豆 #生活", "备忘列表", "搜备忘 咖啡", "删掉备忘 3"],
    rules=[
        Rule("note.search", r"^搜(?:索)?(?:备忘|笔记)?\s*(?P<keyword>.+)$", _search, priority=20),
        Rule("note.delete", r"^删(?:掉)?(?:备忘|笔记)?\s*#?(?P<id>\d+)$", _delete, priority=20),
        Rule("note.list", r"^(?:备忘列表|备忘|笔记列表|看备忘)$", _list, priority=20),
        Rule("note.add", r"^(?:记一?下|记个|帮我记|备忘|速记|note)\s*[:：,，]?\s*(?P<content>.+)$", _add, priority=30),
    ],
)
