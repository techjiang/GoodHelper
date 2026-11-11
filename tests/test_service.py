import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from goodhelper.core.board import render, snapshot
from goodhelper.core.config import Config
from goodhelper.core.scheduler import due_alerts, pending_within
from goodhelper.core.service import Service
from goodhelper.web.app import create_server


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config = Config(home=Path(self._tmp.name))
        self.service = Service(self.config)

    def tearDown(self):
        self.service.close()
        self._tmp.cleanup()

    def test_ask_and_board(self):
        result = self.service.ask("明天下午三点 交周报")
        self.assertIn("交周报", result.text)
        board = self.service.board()
        self.assertIn("明天", board["rendered"])
        self.assertIsInstance(result.latency_ms, int)

    def test_export(self):
        self.service.ask("记一下 导出测试")
        payload = json.loads(self.service.export_json())
        self.assertTrue(payload["notes"])
        self.assertTrue(payload["messages"])

    def test_scheduler_window(self):
        self.service.ask("提醒我 5 分钟后喝水")
        alerts = pending_within(self.service.store, self.config)
        self.assertEqual([a.title for a in alerts], ["喝水"])
        self.assertEqual(pending_within(self.service.store, self.config), [], "同一件事不该提醒两次")

        self.service.ask("提醒我 6 分钟后洗手")
        self.assertEqual([a.title for a in pending_within(self.service.store, self.config)], ["洗手"])

    def test_scheduler_ignores_far_future(self):
        self.service.ask("明天下午三点 开评审会")
        self.assertEqual(due_alerts(self.service.store, self.config), [])

    def test_board_render_empty(self):
        snap = snapshot(self.service.store, self.config)
        text = render(snap)
        self.assertIn("今天没有固定安排", text)


class WebTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config = Config(home=Path(self._tmp.name))
        self.server = create_server(self.config, "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self._tmp.cleanup()

    def test_ask_and_board(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/ask",
            data=json.dumps({"text": "明天九点 晨会"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
        self.assertIn("晨会", data["text"])
        self.assertIn("board", data)

        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/board") as resp:
            board = json.load(resp)
        self.assertTrue(board["tomorrow"])

    def test_empty_ask_rejected(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/ask",
            data=json.dumps({"text": "  "}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_static_index(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as resp:
            body = resp.read().decode("utf-8")
        self.assertIn("好助手", body)


if __name__ == "__main__":
    unittest.main()
