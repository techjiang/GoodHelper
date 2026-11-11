import unittest
from datetime import datetime

from goodhelper.core.clock import cn_to_int, fmt_short, humanize_delta, parse_time

NOW = datetime(2026, 11, 12, 14, 30)  # 周四


class TestCnToInt(unittest.TestCase):
    def test_digits_and_cn(self):
        self.assertEqual(cn_to_int("8"), 8)
        self.assertEqual(cn_to_int("九"), 9)
        self.assertEqual(cn_to_int("十五"), 15)
        self.assertEqual(cn_to_int("二十"), 20)
        self.assertEqual(cn_to_int("二十五"), 25)
        self.assertIsNone(cn_to_int("abc"))
        self.assertIsNone(cn_to_int(None))


class TestParseTime(unittest.TestCase):
    def assertWhen(self, text, expected):
        parsed = parse_time(text, NOW)
        self.assertIsNotNone(parsed, text)
        self.assertEqual(parsed.when, expected, text)
        return parsed

    def test_day_and_clock(self):
        self.assertWhen("明天下午三点提醒我交周报", datetime(2026, 11, 13, 15, 0))
        self.assertWhen("今晚九点", datetime(2026, 11, 12, 21, 0))
        self.assertWhen("明晚九点", datetime(2026, 11, 13, 21, 0))

    def test_relative(self):
        self.assertWhen("10 分钟后喝水", datetime(2026, 11, 12, 14, 40))
        self.assertWhen("十分钟后休息", datetime(2026, 11, 12, 14, 40))
        self.assertWhen("三天后写总结", datetime(2026, 11, 15, 14, 30))

    def test_weekday_and_date(self):
        self.assertWhen("周五 18:00 下班", datetime(2026, 11, 13, 18, 0))
        self.assertWhen("下周周一 9:00 站会", datetime(2026, 11, 16, 9, 0))
        self.assertWhen("3月1日 开会", datetime(2027, 3, 1, 0, 0))

    def test_rest_is_cleaned(self):
        parsed = parse_time("明天下午三点提醒我交周报", NOW)
        self.assertNotIn("明天", parsed.rest)
        self.assertNotIn("三点", parsed.rest)
        self.assertIn("交周报", parsed.rest)

    def test_no_time(self):
        self.assertIsNone(parse_time("帮我记一下这个想法", NOW))


class TestHumanize(unittest.TestCase):
    def test_delta(self):
        self.assertEqual(humanize_delta(datetime(2026, 11, 12, 14, 40), NOW), "10 分钟后")
        self.assertEqual(fmt_short(datetime(2026, 11, 13, 15, 0), NOW), "明天 15:00")
        self.assertEqual(fmt_short(datetime(2026, 12, 1, 9, 0), NOW), "2026-12-01 09:00")


if __name__ == "__main__":
    unittest.main()
