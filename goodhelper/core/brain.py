"""对话引擎：把一句话路由到插件规则，没有命中就走兜底对话。"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime

from goodhelper.core.clock import parse_time
from goodhelper.core.config import Config
from goodhelper.core.plugin import Context, Reply, Rule, SimplePlugin, discover
from goodhelper.core.store import Store

_GREETINGS = ("你好", "您好", "hi", "hello", "嘿", "在吗", "早上好", "晚上好")
_THANKS = ("谢谢", "多谢", "感谢", "thank")
_GREETING_REPLIES = (
    "我在。想记点什么、安排点什么，直接说就行。",
    "在的。今天想先处理哪件事？",
    "随时在。说说看。",
)


@dataclass
class Turn:
    reply: Reply
    latency_ms: int


class Brain:
    def __init__(self, config: Config, store: Store | None = None) -> None:
        self.config = config
        self.store = store or Store(config.db_path)
        self.plugins: list[SimplePlugin] = discover(config.enabled_plugins)
        self._rules: list[tuple[re.Pattern[str], Rule]] = []
        for plugin in sorted(self.plugins, key=lambda p: p.name):
            for rule in plugin.rule_list():
                self._rules.append((rule.compiled(), rule))

    # ---- 路由 ----
    def route(self, text: str) -> Rule | None:
        for pattern, rule in self._rules:
            if pattern.search(text):
                return rule
        return None

    def handle(self, text: str, source: str = "cli") -> Turn:
        started = time.perf_counter()
        text = (text or "").strip()
        if not text:
            return Turn(Reply("我在听着，说点什么都行。", "empty"), 0)

        ctx = Context(store=self.store, config=self.config, text=text, source=source)
        rule = self.route(text)
        if rule is not None:
            match = rule.compiled().search(text)
            assert match is not None
            try:
                reply = rule.handler(ctx, match)
            except Exception as exc:  # noqa: BLE001 —— 插件出错也不能让整轮对话中断
                reply = Reply(f"这条我没处理好：{exc}", intent=f"{rule.intent}.error")
            reply.intent = reply.intent or rule.intent
        else:
            reply = self._fallback(ctx)

        latency = int((time.perf_counter() - started) * 1000)
        self._remember("user", text, "")
        self._remember("assistant", reply.text, reply.intent)
        return Turn(reply, latency)

    def _fallback(self, ctx: Context) -> Reply:
        text = ctx.text
        lowered = text.lower()
        if any(word in lowered for word in _GREETINGS):
            return Reply(self._pick(_GREETING_REPLIES), "chat.greeting")
        if any(word in lowered for word in _THANKS):
            return Reply("不用客气。还有别的事，一并说。", "chat.thanks")
        if text.endswith(("吗？", "吗")):
            return Reply("这个我判断不了。不过你要是把它记成待办，我可以按时提醒你。", "chat.question")

        # 带时间表达的一句话，直接当成日程/待办接住
        parsed = parse_time(text)
        if parsed is not None:
            body = parsed.rest or text
            date_str = parsed.when.isoformat(timespec="minutes")
            self.store.execute(
                "INSERT INTO events(title, start_at, duration, created_at) VALUES(?, ?, 0, ?)",
                (body, date_str, datetime.now().isoformat(timespec="seconds")),
            )
            return Reply(
                f"听起来像件有时有晌的事，我先按「{body}」记在 {date_str.replace('T', ' ')} 了。",
                "agenda.auto",
                {"title": body, "start_at": date_str},
            )

        return Reply(
            self._pick((
                "我记住了这句话。要提醒你的话，加上时间，比如「明天九点提醒我交周报」。",
                "收到。想让它变成待办或日程，说一句「明天下午三点 写方案」就行。",
                "记下了。也可以问我看板：输入「/board」。",
            )),
            "chat.capture",
            {"captured": text},
        )

    def _pick(self, options: tuple[str, ...]) -> str:
        idx = self.store.scalar("SELECT COUNT(*) FROM messages") % len(options)
        return options[int(idx)]

    def _remember(self, role: str, content: str, intent: str) -> None:
        self.store.execute(
            "INSERT INTO messages(role, content, intent, created_at) VALUES(?, ?, ?, ?)",
            (role, content, intent, datetime.now().isoformat(timespec="seconds")),
        )

    def history(self, limit: int = 20) -> list[dict]:
        rows = self.store.query(
            "SELECT role, content, intent, created_at FROM messages ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in reversed(rows)]
