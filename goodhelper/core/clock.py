"""时间解析：把「明天下午三点」「周五 18:00」「10 分钟后」这类中文表达转成绝对时间。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

MINUTE = 60
HOUR = 3600
DAY = 86400

_WEEKDAYS = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6,
             "1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "7": 6}
_CN_DIGITS = {"零": 0, "一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}

_NUM = r"(?:\d{1,3}|[零一两二三四五六七八九十]{1,3})"
_REL = re.compile(
    rf"(?P<num>{_NUM})\s*(?P<unit>秒钟?|分钟|分|个?小时|钟头|天|日|周|个?星期|个月)\s*(?:之后|以后|后)?"
)
_DAYWORD = re.compile(r"(?P<day>大后天|后天|明天|明日|今天|今日|今晚|明晚|今早|明早)")
_WEEK = re.compile(r"(?P<prefix>下下|下|本|这个|这)?\s*(?:周|星期|礼拜)\s*(?P<wd>[一二三四五六日天1-7])")
_MONTH_DAY = re.compile(r"(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*[日号]?")
_CLOCK = re.compile(
    rf"(?P<hour>{_NUM})\s*(?:[:：]\s*(?P<minute>\d{{1,2}})|点\s*(?:(?P<half>半)|(?P<minute2>{_NUM})\s*分?)?)"
)
_PERIOD = re.compile(r"(?P<period>凌晨|早上|上午|中午|下午|傍晚|晚上)")

_DAY_WORDS = {"今天": 0, "今日": 0, "今晚": 0, "今早": 0,
              "明天": 1, "明日": 1, "明晚": 1, "明早": 1,
              "后天": 2, "大后天": 3}
_PERIOD_HOUR = {"凌晨": 5, "早上": 8, "上午": 9, "中午": 12, "下午": 15, "傍晚": 18, "晚上": 20}


@dataclass
class ParsedTime:
    when: datetime
    # 去掉时间表达后剩余的文本，用作事项标题
    rest: str


def cn_to_int(text: str | None) -> int | None:
    """把「十五」「二十」「8」这类数字转成 int，无法识别返回 None。"""
    if not text:
        return None
    text = text.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if "十" in text:
        head, _, tail = text.partition("十")
        tens = 1 if head == "" else _CN_DIGITS.get(head)
        ones = 0 if tail == "" else _CN_DIGITS.get(tail)
        if tens is None or ones is None:
            return None
        return tens * 10 + ones
    if len(text) == 1:
        return _CN_DIGITS.get(text)
    return None


def _unit_seconds(unit: str) -> int:
    if unit.startswith("秒"):
        return 1
    if unit in ("分钟", "分"):
        return MINUTE
    if unit.endswith("小时") or unit == "钟头":
        return HOUR
    if unit.endswith("星期") or unit == "周":
        return 7 * DAY
    if unit == "个月":
        return 30 * DAY
    return DAY


def _strip_spans(text: str, spans: list[tuple[int, int]], extra: tuple[str, ...] = ()) -> str:
    rest = text
    for start, end in sorted(spans, reverse=True):
        rest = rest[:start] + " " + rest[end:]
    for token in extra:
        rest = rest.replace(token, " ")
    return re.sub(r"\s{2,}", " ", rest).strip(" ，,。、:：后")


def parse_time(text: str, now: datetime | None = None) -> ParsedTime | None:
    """从文本里解析出一个时间点，解析不到返回 None。"""
    now = (now or datetime.now()).replace(second=0, microsecond=0)
    spans: list[tuple[int, int]] = []
    anchor: datetime | None = None
    extras: list[str] = []

    def take(m: re.Match[str]) -> None:
        spans.append(m.span())
        if m.group(0).endswith("后"):
            extras.append("后")

    # 相对偏移：20 分钟后 / 三天后
    for m in _REL.finditer(text):
        num = cn_to_int(m.group("num"))
        if num is None:
            continue
        anchor = (anchor or now) + timedelta(seconds=num * _unit_seconds(m.group("unit")))
        take(m)
        extras.append(m.group(0))

    day_m = _DAYWORD.search(text)
    if day_m:
        base = anchor or now
        anchor = base + timedelta(days=_DAY_WORDS[day_m.group("day")])
        take(day_m)

    week_m = _WEEK.search(text)
    if week_m:
        target = _WEEKDAYS.get(week_m.group("wd"))
        if target is not None:
            base = anchor or now
            start = datetime.combine(base.date(), datetime.min.time())
            forward = (target - start.weekday()) % 7 or 7
            if (week_m.group("prefix") or "") in ("下", "下下"):
                if forward < 7:
                    forward += 7
                if week_m.group("prefix") == "下下":
                    forward += 7
            anchor = start + timedelta(days=forward)
            take(week_m)

    md_m = _MONTH_DAY.search(text)
    if md_m:
        try:
            picked = datetime(now.year, int(md_m.group("month")), int(md_m.group("day")))
        except ValueError:
            picked = None
        if picked is not None:
            if picked.date() < now.date():
                picked = picked.replace(year=now.year + 1)
            anchor = picked
            take(md_m)

    period_m = _PERIOD.search(text)
    # 「今晚」「明晚」自带晚上语义
    implicit_period = "晚上" if (not period_m and day_m and day_m.group("day").endswith("晚")) else None
    if period_m:
        take(period_m)

    clock_m = _CLOCK.search(text)
    if clock_m:
        hour = cn_to_int(clock_m.group("hour"))
        minute = 0
        if clock_m.group("half"):
            minute = 30
        else:
            raw_minute = clock_m.group("minute") or clock_m.group("minute2")
            if raw_minute:
                minute = cn_to_int(raw_minute) or 0
        if hour is not None and hour < 24 and minute < 60:
            period = period_m.group("period") if period_m else implicit_period
            if period:
                # 「下午三点」是 15 点；「中午」只在 11 点前补 12
                afternoon = period in ("下午", "傍晚", "晚上") and hour < 12
                noon = period == "中午" and hour < 11
                if afternoon or noon:
                    hour += 12
                elif period == "凌晨" and hour == 12:
                    hour = 0
            day = (anchor or now).date()
            candidate = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)
            if anchor is None and candidate <= now:
                candidate += timedelta(days=1)
            anchor = candidate
            take(clock_m)
    elif anchor and (period_m or implicit_period):
        key = period_m.group("period") if period_m else implicit_period
        anchor = anchor.replace(hour=_PERIOD_HOUR[key], minute=0)

    if anchor is None:
        return None
    return ParsedTime(when=anchor, rest=_strip_spans(text, spans, tuple(extras)))


def humanize_delta(target: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    delta = (target - now).total_seconds()
    future = delta >= 0
    delta = abs(delta)
    if delta < MINUTE:
        body = "不到 1 分钟"
    elif delta < HOUR:
        body = f"{int(delta // MINUTE)} 分钟"
    elif delta < 6 * HOUR:
        hours, rest = divmod(int(delta), HOUR)
        body = f"{hours} 小时{f' {rest // MINUTE} 分' if rest >= 60 else ''}"
    elif delta < DAY:
        body = f"{int(delta // HOUR)} 小时"
    elif delta < 30 * DAY:
        body = f"{int(delta // DAY)} 天"
    else:
        body = f"{int(delta // (30 * DAY))} 个月"
    return f"{body}后" if future else f"{body}前"


def fmt(dt: datetime | None) -> str:
    if dt is None:
        return "未定"
    if dt.hour == 0 and dt.minute == 0:
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d %H:%M")


def fmt_short(dt: datetime, now: datetime | None = None) -> str:
    """今天/明天用口语写法，其它给完整日期。"""
    now = now or datetime.now()
    label = {0: "今天", 1: "明天", 2: "后天"}.get((dt.date() - now.date()).days, "")
    clock = dt.strftime("%H:%M") if (dt.hour or dt.minute) else ""
    if label:
        return f"{label} {clock}".strip()
    return fmt(dt) if clock else dt.strftime("%Y-%m-%d")
