import tempfile
import unittest
from pathlib import Path

from goodhelper.core.brain import Brain
from goodhelper.core.config import Config


def make_brain(tmp: str) -> Brain:
    config = Config(home=Path(tmp), enabled_plugins=["note", "todo", "agenda", "kb", "calc", "help"])
    return Brain(config)


class BrainTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.brain = make_brain(self._tmp.name)

    def tearDown(self):
        self.brain.store.close()
        self._tmp.cleanup()

    def ask(self, text):
        return self.brain.handle(text)

    def test_note_roundtrip(self):
        reply = self.ask("记一下 想买咖啡豆 #生活")
        self.assertEqual(reply.reply.intent, "note.add")
        self.assertIn("咖啡豆", reply.reply.text)
        listing = self.ask("备忘列表")
        self.assertIn("咖啡豆", listing.reply.text)
        self.assertIn("生活", listing.reply.text)
        found = self.ask("搜备忘 咖啡")
        self.assertIn("咖啡豆", found.reply.text)

    def test_note_delete(self):
        self.ask("记一下 临时想法")
        deleted = self.ask("删掉备忘 1")
        self.assertEqual(deleted.reply.intent, "note.delete")
        self.assertIn("没找到", self.ask("搜备忘 临时").reply.text)

    def test_todo_lifecycle(self):
        added = self.ask("待办 明天下午三点 写周报 紧急")
        self.assertEqual(added.reply.intent, "todo.add")
        listing = self.ask("待办列表")
        self.assertIn("写周报", listing.reply.text)
        self.assertIn("[高]", listing.reply.text)
        done = self.ask("完成 1")
        self.assertEqual(done.reply.intent, "todo.done")
        self.assertIn("清空了", self.ask("待办列表").reply.text)
        self.assertIn("1 条", self.ask("清理已完成").reply.text)

    def test_agenda(self):
        added = self.ask("明天下午三点 开会")
        self.assertEqual(added.reply.intent, "agenda.add")
        agenda = self.ask("日程")
        self.assertIn("开会", agenda.reply.text)
        nxt = self.ask("下一件事")
        self.assertIn("开会", nxt.reply.text)
        cancelled = self.ask("取消日程 1")
        self.assertIn("取消", cancelled.reply.text)

    def test_remind_keeps_title_clean(self):
        reply = self.ask("提醒我 10 分钟后喝水")
        self.assertIn("喝水", reply.reply.text)
        self.assertNotIn("提醒我", reply.reply.text)

    def test_calc(self):
        self.assertIn("2", self.ask("1+1").reply.text)
        self.assertIn("84", self.ask("算 12*(3+4)").reply.text)
        self.assertIn("算不了", self.ask("算 __import__('os')").reply.text)

    def test_help_and_chat(self):
        self.assertIn("速记", self.ask("帮助").reply.text)
        self.assertEqual(self.ask("你好").reply.intent, "chat.greeting")
        captured = self.ask("随手说一句没什么信息的话")
        self.assertEqual(captured.reply.intent, "chat.capture")

    def test_history_recorded(self):
        self.ask("记一下 历史测试")
        history = self.brain.history(10)
        self.assertGreaterEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")


class KnowledgeBaseTest(unittest.TestCase):
    def test_kb_ask(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            kb = home / "kb"
            kb.mkdir()
            (kb / "pipeline.md").write_text(
                "# 流水线\n\n云原生构建用 .cnb.yml 描述流水线，push 事件会触发构建。\n",
                encoding="utf-8",
            )
            brain = make_brain(tmp)
            try:
                reply = brain.handle("知识库 怎么配置流水线")
                self.assertEqual(reply.reply.intent, "kb.ask")
                self.assertIn("cnb.yml", reply.reply.text)
                self.assertIn("1 个文件", brain.handle("知识库状态").reply.text)
            finally:
                brain.store.close()


if __name__ == "__main__":
    unittest.main()
