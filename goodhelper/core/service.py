"""对外统一服务门面：CLI 和 Web 都只跟它打交道。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from goodhelper.core import board as board_mod
from goodhelper.core.brain import Brain, Turn
from goodhelper.core.config import Config
from goodhelper.core.scheduler import pending_within


@dataclass
class AskResult:
    text: str
    intent: str
    data: dict | None
    latency_ms: int
    alerts: list[str]


class Service:
    def __init__(self, config: Config, brain: Brain | None = None) -> None:
        self.config = config
        self.brain = brain or Brain(config)
        self.store = self.brain.store

    # ---- 对话 ----
    def ask(self, text: str, source: str = "cli") -> AskResult:
        now = datetime.now()
        alert_objects = pending_within(self.store, self.config, now)
        turn: Turn = self.brain.handle(text, source=source)
        alerts = [alert.as_line(now) for alert in alert_objects]
        return AskResult(turn.reply.text, turn.reply.intent, turn.reply.data, turn.latency_ms, alerts)

    def board(self) -> dict:
        snap = board_mod.snapshot(self.store, self.config)
        snap["rendered"] = board_mod.render(snap, self.config.user_name)
        snap["now"] = snap["now"].isoformat(timespec="minutes")
        return snap

    def history(self, limit: int = 30) -> list[dict]:
        return self.brain.history(limit)

    def export(self) -> dict:
        return {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "notes": [dict(r) for r in self.store.query("SELECT * FROM notes WHERE deleted = 0")],
            "todos": [dict(r) for r in self.store.query("SELECT * FROM todos")],
            "events": [dict(r) for r in self.store.query("SELECT * FROM events WHERE cancelled = 0")],
            "messages": [dict(r) for r in self.store.query("SELECT * FROM messages ORDER BY id")],
        }

    def export_json(self) -> str:
        return json.dumps(self.export(), ensure_ascii=False, indent=2)

    def close(self) -> None:
        self.store.close()
