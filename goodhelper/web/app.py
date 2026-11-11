"""零依赖 Web 服务：HTTP 路由 + 静态资源，提供聊天、看板、导出接口。"""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from goodhelper.core.config import Config
from goodhelper.core.service import Service

STATIC_DIR = Path(__file__).parent / "static"
MAX_BODY = 64 * 1024


def make_handler(service: Service) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GoodHelper"

        # ---- 基础工具 ----
        def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path) -> None:
            if not path.is_file() or STATIC_DIR not in path.resolve().parents:
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            data = path.read_bytes()
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {}

        def log_message(self, fmt: str, *args) -> None:  # 安静一点，别刷屏
            return

        # ---- 路由 ----
        def do_GET(self) -> None:
            route = urlparse(self.path).path
            if route in ("/", "/index.html"):
                self._send_file(STATIC_DIR / "index.html")
            elif route == "/api/board":
                self._send_json(service.board())
            elif route == "/api/history":
                self._send_json({"messages": service.history(40)})
            elif route == "/api/export":
                self._send_json(service.export())
            elif route == "/api/health":
                self._send_json({"ok": True, "name": service.config.name})
            else:
                self._send_file(STATIC_DIR / route.lstrip("/"))

        def do_POST(self) -> None:
            route = urlparse(self.path).path
            if route != "/api/ask":
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            payload = self._read_json()
            text = str(payload.get("text", "")).strip()
            if not text:
                self._send_json({"error": "说点什么吧"}, HTTPStatus.BAD_REQUEST)
                return
            result = service.ask(text, source="web")
            self._send_json(
                {
                    "text": result.text,
                    "intent": result.intent,
                    "data": result.data,
                    "latency_ms": result.latency_ms,
                    "alerts": result.alerts,
                    "board": service.board(),
                }
            )

    return Handler


def create_server(config: Config, host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
    service = Service(config)
    handler = make_handler(service)
    return ThreadingHTTPServer((host or config.web_host, port or config.web_port), handler)


def serve(config: Config, host: str | None = None, port: int | None = None) -> int:
    server = create_server(config, host, port)
    addr, real_port = server.server_address[:2]
    print(f"{config.name} 已在 http://{addr}:{real_port} 待命，Ctrl-C 收工。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n收工。")
    finally:
        server.shutdown()
        server.server_close()
    return 0
