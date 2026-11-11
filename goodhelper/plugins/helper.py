"""帮助与自我介绍：让新用户两分钟摸清能干什么。"""

from __future__ import annotations

from goodhelper.core.plugin import Context, Reply, Rule, SimplePlugin, discover


def build_help(config) -> str:
    lines = ["我是一只本地跑的小助手，会这几件事：", ""]
    for plugin in discover(list(getattr(config, "enabled_plugins", []) or [])):
        if plugin.name == "help":
            continue
        lines.append(f"[{plugin.title}]")
        lines.extend(f"  · {item}" for item in plugin.help)
        lines.append("")
    lines.append("其它话我也接得住，只是会先收着。输入 /board 看看今日看板。")
    return "\n".join(lines)


def _help(ctx: Context, match) -> Reply:
    return Reply(build_help(ctx.config), "helper.help")


def _about(ctx: Context, match) -> Reply:
    name = getattr(ctx.config, "name", "好助手")
    return Reply(
        f"我是{name}，一只装在你自己机器上的助手。数据都存在本地 SQLite，不联网也能用。",
        "helper.about",
    )


PLUGIN = SimplePlugin(
    name="help",
    title="帮助",
    help=["帮助", "你是谁"],
    rules=[
        Rule("helper.help", r"^(?:帮助|help|能做什么|怎么用|/help)$", _help, priority=5),
        Rule("helper.about", r"^(?:你是谁|介绍一下自己|about)$", _about, priority=5),
    ],
)
