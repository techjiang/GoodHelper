"""插件协议：一个插件 = 一组意图规则 + 处理函数。

插件只需暴露 `PLUGIN`（Plugin 实例），引擎启动时自动发现，
新增能力不用改路由、不用改 UI。
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from goodhelper.core.store import Store


@dataclass
class Context:
    """一次请求的上下文。"""

    store: Store
    config: object  # goodhelper.core.config.Config
    text: str
    source: str = "cli"  # cli / web / scheduler


@dataclass
class Reply:
    text: str
    intent: str
    data: dict | None = None
    # 需要落库的助手回复之外的副作用（例如待确认动作），交给调用方处理
    meta: dict = field(default_factory=dict)


Handler = Callable[[Context, re.Match[str]], Reply]


@dataclass
class Rule:
    intent: str
    pattern: str
    handler: Handler
    priority: int = 100  # 数字小的先匹配
    description: str = ""

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern, re.IGNORECASE)


class Plugin(Protocol):
    name: str
    title: str
    help: list[str]


@dataclass
class SimplePlugin:
    """插件的最小实现：名字 + 一行帮助 + 若干规则。"""

    name: str
    title: str
    rules: list[Rule]
    help: list[str] = field(default_factory=list)

    def rule_list(self) -> list[Rule]:
        return sorted(self.rules, key=lambda r: r.priority)


def discover(enabled: list[str]) -> list[SimplePlugin]:
    """导入 goodhelper.plugins 下所有声明了 PLUGIN 的模块。"""
    from goodhelper import plugins as plugins_pkg

    found: list[SimplePlugin] = []
    for info in pkgutil.iter_modules(plugins_pkg.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{plugins_pkg.__name__}.{info.name}")
        plugin = getattr(module, "PLUGIN", None)
        if plugin is None:
            continue
        if enabled and plugin.name not in enabled:
            continue
        found.append(plugin)
    return found
