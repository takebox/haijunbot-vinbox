# -*- coding: utf-8 -*-
"""Cron expression parsing and next match time calculation tests."""

from __future__ import annotations

from datetime import datetime

import pytest

from haijunbot.haijunbot_web_gateway.cron import CronParseError
from haijunbot.haijunbot_web_gateway.cron import cron_next_match
from haijunbot.haijunbot_web_gateway.cron import parse_cron


def _ts(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> float:
    return datetime(year, month, day, hour, minute).timestamp()


def _next(expr: str, from_ts: float) -> datetime:
    return datetime.fromtimestamp(cron_next_match(expr, from_ts))


def test_every_minute() -> None:
    n = _next("* * * * *", _ts(2026, 10, 2, 13, 54))
    assert n == datetime(2026, 10, 2, 13, 55)


def test_daily_at_nine() -> None:
    n = _next("0 9 * * *", _ts(2026, 10, 2, 13, 54))
    assert n == datetime(2026, 10, 3, 9, 0)


def test_weekly_monday_nine() -> None:
    # 2026-10-02 is a Friday; day-of-month field is *, weekday field is restricted -> only match on Monday
    n = _next("0 9 * * 1", _ts(2026, 10, 2, 13, 54))
    assert n == datetime(2026, 10, 5, 9, 0)
    assert n.weekday() == 0  # Monday


def test_weekday_zero_is_sunday() -> None:
    # 2026-10-04 is a Sunday
    n = _next("0 0 * * 0", _ts(2026, 10, 2, 13, 54))
    assert n == datetime(2026, 10, 4, 0, 0)
    assert n.weekday() == 6  # Sunday


def test_weekday_seven_is_sunday() -> None:
    n = _next("0 0 * * 7", _ts(2026, 10, 2, 13, 54))
    assert n == datetime(2026, 10, 4, 0, 0)


def test_day_of_month() -> None:
    n = _next("0 0 1 * *", _ts(2026, 10, 2, 13, 54))
    assert n == datetime(2026, 11, 1, 0, 0)


def test_day_or_weekday_both_restricted() -> None:
    # Both day-of-month and weekday fields are restricted -> OR: 1st of each month or Sunday
    n = _next("0 0 1 * 0", _ts(2026, 10, 2, 13, 54))
    # 2026-10-04 is a Sunday, earlier than 11-01
    assert n == datetime(2026, 10, 4, 0, 0)


def test_step_minutes() -> None:
    n = _next("*/15 * * * *", _ts(2026, 10, 2, 13, 54))
    assert n == datetime(2026, 10, 2, 14, 0)


def test_range_with_step() -> None:
    # 1-59/2 minutes -> odd minutes
    n = _next("1-59/2 * * * *", _ts(2026, 10, 2, 13, 54))
    assert n.minute == 55


def test_list_field() -> None:
    n = _next("5,10,15 * * * *", _ts(2026, 10, 2, 13, 54))
    assert n.minute == 5


def test_leap_year_feb_29() -> None:
    # 2028 is a leap year
    n = _next("0 0 29 2 *", _ts(2026, 10, 2, 13, 54))
    assert n == datetime(2028, 2, 29, 0, 0)


def test_invalid_month_day_skipped() -> None:
    # 31st of each month: months without a 31st (like April) are skipped until the next month that has one
    n = _next("0 0 31 * *", _ts(2026, 10, 2, 13, 54))
    assert n == datetime(2026, 10, 31, 0, 0)


def test_feb_30_never_matches() -> None:
    # February 30th never exists, should raise CronParseError
    with pytest.raises(CronParseError):
        cron_next_match("0 0 30 2 *", _ts(2026, 10, 2, 13, 54))


@pytest.mark.parametrize(
    "bad",
    [
        "* * * *",  # Only 4 segments
        "60 * * * *",  # Minute out of range
        "a * * * *",  # Invalid character
        "0 0 0 * *",  # Day out of range
        "*/0 * * * *",  # Step of 0
        "",  # Empty
    ],
)
def test_invalid_expressions_raise(bad: str) -> None:
    with pytest.raises(CronParseError):
        parse_cron(bad)


def test_parse_cron_returns_schedule() -> None:
    schedule = parse_cron("0 9 * * 1")
    assert schedule.expression == "0 9 * * 1"
    assert schedule.minutes == [0]
    assert schedule.hours == [9]
    assert schedule.weekdays == [0]  # Monday
