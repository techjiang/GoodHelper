"""命令行入口：goodhelper ask / board / serve / remind / export / init。"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from goodhelper import __version__
from goodhelper.core.config import Config, load_config
from goodhelper.core.scheduler import pending_within
from goodhelper.core.service import Service

BANNER = r"""
  ___                 _   _   _      _
 / __|___  ___  ___ __| |_| |_| |_  _| |___
| (_ / _ \/ _ \/ _ \ _` | ' \  _ \/ _` / -_)
 \___\___/\___/\___/__,_|_||_\___/\__,_\___|
"""

SAMPLE_CONFIG = """# 好助手配置
[assistant]
name = "好助手"
user_name = "朋友"
remind_before = 10

[web]
host = "127.0.0.1"
port = 8321

[plugins]
enabled = ["note", "todo", "agenda", "kb", "calc", "help"]
"""


def _service(args: argparse.Namespace) -> Service:
    config: Config = load_config(args.config)
    return Service(config)


def _print_alerts(alerts: list[str]) -> None:
    if not alerts:
        return
    print("\n该动了 —— ")
    for line in alerts:
        print(f"  ⏰ {line}")
    print()


def cmd_ask(args: argparse.Namespace) -> int:
    service = _service(args)
    try:
        if not sys.stdin.isatty() and not args.text:
            text = sys.stdin.read().strip()
            result = service.ask(text, source="pipe")
            _print_alerts(result.alerts)
            print(result.text)
            return 0

        text = " ".join(args.text).strip()
        if text:
            result = service.ask(text)
            _print_alerts(result.alerts)
            print(result.text)
            return 0

        print(BANNER)
        print("输入 /board 看板、/help 帮助、/quit 退出。")
        while True:
            try:
                line = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not line:
                continue
            if line in ("/quit", "/exit", "quit", "exit"):
                print("回头见。")
                return 0
            if line == "/board":
                print(Service(service.config, service.brain).board()["rendered"])
                continue
            result = service.ask(line)
            _print_alerts(result.alerts)
            print(result.text)
    finally:
        service.close()


def cmd_board(args: argparse.Namespace) -> int:
    service = _service(args)
    try:
        print(service.board()["rendered"])
        return 0
    finally:
        service.close()


def cmd_remind(args: argparse.Namespace) -> int:
    service = _service(args)
    try:
        if not args.watch:
            alerts = pending_within(service.store, service.config)
            if not alerts:
                print("眼下没有要提醒的事。")
            _print_alerts([a.as_line() for a in alerts])
            return 0

        print(f"盯着日程，每 {args.interval} 秒看一次，Ctrl-C 退出。")
        while True:
            for alert in pending_within(service.store, service.config):
                print(f"{datetime.now():%H:%M} ⏰ {alert.as_line()}", flush=True)
            time.sleep(max(args.interval, 5))
    except KeyboardInterrupt:
        print("\n不盯了。")
        return 0
    finally:
        service.close()


def cmd_serve(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    host = args.host or config.web_host
    port = config.web_port if args.port is None else args.port
    from goodhelper.web.app import serve

    return serve(config, host=host, port=port)


def cmd_export(args: argparse.Namespace) -> int:
    service = _service(args)
    try:
        payload = service.export_json()
        if args.out:
            Path(args.out).write_text(payload, encoding="utf-8")
            print(f"已导出到 {args.out}")
        else:
            print(payload)
        return 0
    finally:
        service.close()


def cmd_init(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    config.home.mkdir(parents=True, exist_ok=True)
    config.kb_dir.mkdir(parents=True, exist_ok=True)
    target = config.home / "config.toml"
    if target.exists() and not args.force:
        print(f"{target} 已存在，加 --force 覆盖。")
        return 1
    target.write_text(SAMPLE_CONFIG, encoding="utf-8")
    print(f"配置写好了：{target}")
    print(f"知识库目录：{config.kb_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="goodhelper", description="好助手：本地优先的智能助理")
    parser.add_argument("--version", action="version", version=f"goodhelper {__version__}")
    parser.add_argument("-c", "--config", help="配置文件路径", default=None)
    sub = parser.add_subparsers(dest="command")

    ask = sub.add_parser("ask", help="问一句，或进入交互对话")
    ask.add_argument("text", nargs="*", help="要问的话")
    ask.set_defaults(func=cmd_ask)

    board = sub.add_parser("board", help="打印今日看板")
    board.set_defaults(func=cmd_board)

    remind = sub.add_parser("remind", help="查看或持续监听提醒")
    remind.add_argument("--watch", action="store_true", help="持续监听")
    remind.add_argument("--interval", type=int, default=30, help="监听间隔秒数")
    remind.set_defaults(func=cmd_remind)

    serve = sub.add_parser("serve", help="启动 Web 界面")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.set_defaults(func=cmd_serve)

    export = sub.add_parser("export", help="导出全部数据为 JSON")
    export.add_argument("-o", "--out", help="输出文件，缺省打印到标准输出")
    export.set_defaults(func=cmd_export)

    init = sub.add_parser("init", help="生成配置骨架")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        args = parser.parse_args([*(argv or []), "ask"])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
