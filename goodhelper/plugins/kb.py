"""知识库：把 Markdown 笔记切片索引，用 BM25 检索并给出答案原文。"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from goodhelper.core.plugin import Context, Reply, Rule, SimplePlugin

SUPPORTED = {".md", ".markdown", ".txt"}
_TOKEN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fa5]")


@dataclass
class Chunk:
    source: str
    heading: str
    text: str
    tokens: Counter


def tokenize(text: str) -> Counter:
    return Counter(_TOKEN.findall(text.lower()))


def load_chunks(root: Path, size: int = 400) -> list[Chunk]:
    chunks: list[Chunk] = []
    if not root.is_dir():
        return chunks
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in SUPPORTED or not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8", errors="ignore")
        heading = path.stem
        buffer: list[str] = []
        for line in raw.splitlines():
            if line.startswith("#"):
                heading = line.lstrip("# ").strip() or heading
            buffer.append(line)
            if sum(len(x) for x in buffer) >= size:
                text = "\n".join(buffer).strip()
                if text:
                    chunks.append(Chunk(str(path.relative_to(root)), heading, text, tokenize(text)))
                buffer = []
        text = "\n".join(buffer).strip()
        if text:
            chunks.append(Chunk(str(path.relative_to(root)), heading, text, tokenize(text)))
    return chunks


def bm25(query: Counter, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75) -> list[tuple[float, Chunk]]:
    if not chunks:
        return []
    avg_len = sum(sum(c.tokens.values()) for c in chunks) / len(chunks)
    df = Counter()
    for chunk in chunks:
        for token in chunk.tokens:
            df[token] += 1
    n = len(chunks)
    scored: list[tuple[float, Chunk]] = []
    for chunk in chunks:
        length = sum(chunk.tokens.values()) or 1
        score = 0.0
        for token, qty in query.items():
            tf = chunk.tokens.get(token, 0)
            if not tf:
                continue
            idf = math.log(1 + (n - df[token] + 0.5) / (df[token] + 0.5))
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * length / avg_len)) * min(qty, 3)
        if score > 0:
            scored.append((score, chunk))
    return sorted(scored, key=lambda item: item[0], reverse=True)


def strip_markdown(text: str) -> str:
    """去掉标题井号与强调符号，只留下能直接读的正文。"""
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return re.sub(r"[`>]", "", text)


def _ask(ctx: Context, match: re.Match[str]) -> Reply:
    question = (match.group("question") or "").strip()
    root = Path(getattr(ctx.config, "kb_dir", Path("kb")))
    chunks = load_chunks(root)
    if not chunks:
        return Reply(
            f"知识库还是空的。把 Markdown 放进 {root}，再来问我。",
            "kb.ask.empty",
            {"dir": str(root)},
        )
    hits = bm25(tokenize(question), chunks)[:3]
    if not hits:
        return Reply(f"知识库里没找到和「{question}」相关的内容。", "kb.ask.miss")
    top_score, top = hits[0]
    excerpt = re.sub(r"\s+", " ", strip_markdown(top.text))[:220]
    others = "、".join(f"{c.heading}（{c.source}）" for _, c in hits[1:])
    tail = f"\n其它相关：{others}" if others else ""
    return Reply(
        f"《{top.heading}》里提到：{excerpt}{tail}",
        "kb.ask",
        {"source": top.source, "score": round(top_score, 3), "hits": len(hits)},
    )


def _stats(ctx: Context, match: re.Match[str]) -> Reply:
    root = Path(getattr(ctx.config, "kb_dir", Path("kb")))
    chunks = load_chunks(root)
    sources = {c.source for c in chunks}
    if not chunks:
        return Reply(f"知识库是空的，目录：{root}", "kb.stats")
    return Reply(f"知识库有 {len(sources)} 个文件、{len(chunks)} 个片段。", "kb.stats")


PLUGIN = SimplePlugin(
    name="kb",
    title="知识库",
    help=["知识库 怎么配流水线", "知识库状态"],
    rules=[
        Rule("kb.stats", r"^知识库(?:状态|统计)$", _stats, priority=10),
        Rule("kb.ask", r"^(?:查知识库|知识库|kb)\s*[:：]?\s*(?P<question>.+)$", _ask, priority=15),
    ],
)
