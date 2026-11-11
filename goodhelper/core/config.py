"""配置加载：TOML 配置文件 + 环境变量覆盖。"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_HOME = "~/.goodhelper"
ENV_HOME = "GOODHELPER_HOME"
ENV_CONFIG = "GOODHELPER_CONFIG"
DEFAULT_PLUGINS = ["note", "todo", "agenda", "kb", "calc", "help"]


@dataclass
class Config:
    home: Path
    name: str = "好助手"
    user_name: str = "朋友"
    web_host: str = "127.0.0.1"
    web_port: int = 8321
    # 需要提前多少分钟提醒日程
    remind_before: int = 10
    # 允许调用的插件名；空表示全部已加载插件
    enabled_plugins: list[str] = field(default_factory=lambda: list(DEFAULT_PLUGINS))
    source: str = "默认配置"

    @property
    def db_path(self) -> Path:
        return self.home / "goodhelper.db"

    @property
    def kb_dir(self) -> Path:
        return self.home / "kb"


def _coerce(raw: dict, home: Path, source: str) -> Config:
    assistant = raw.get("assistant", {})
    web = raw.get("web", {})
    plugins = raw.get("plugins", {})
    cfg = Config(
        home=home,
        name=str(assistant.get("name", "好助手")),
        user_name=str(assistant.get("user_name", "朋友")),
        web_host=str(web.get("host", "127.0.0.1")),
        web_port=int(web.get("port", 8321)),
        remind_before=int(assistant.get("remind_before", 10)),
        enabled_plugins=list(plugins.get("enabled", DEFAULT_PLUGINS)),
        source=source,
    )
    return cfg


def resolve_home() -> Path:
    return Path(os.path.expanduser(os.environ.get(ENV_HOME) or DEFAULT_HOME))


def load_config(explicit: str | None = None) -> Config:
    """按「显式参数 → 环境变量路径 → $GOODHELPER_HOME/config.toml → ~/.goodhelper/config.toml」查找配置。"""
    home = resolve_home()
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(os.path.expanduser(explicit)))
    if os.environ.get(ENV_CONFIG):
        candidates.append(Path(os.path.expanduser(os.environ[ENV_CONFIG])))
    candidates.append(home / "config.toml")

    for path in candidates:
        if path.is_file():
            with path.open("rb") as fp:
                return _coerce(tomllib.load(fp), home, str(path))
    return Config(home=home)
