"""Business-day arithmetic for the Reg E deadline: weekends and US federal holidays do not count.

The holiday rules live only here (12 CFR 1005.2(d) counts a "business day" as any day the institution is open
for substantially all business functions; this prototype treats Saturdays, Sundays and the eleven federal
holidays as closed). Dates are ISO strings (YYYY-MM-DD) at the edges because that is how the app stores them.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import cache

REG_E_BUSINESS_DAYS = 10

MONDAY, THURSDAY, SATURDAY, SUNDAY = 0, 3, 5, 6


def today() -> date:
    """The date "business days left" is measured against. Tests monkeypatch this."""
    return date.today()


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    """A fixed-date holiday on a Saturday is observed the Friday before; on a Sunday, the Monday after."""
    if day.weekday() == SATURDAY:
        return day - timedelta(days=1)
    if day.weekday() == SUNDAY:
        return day + timedelta(days=1)
    return day


@cache
def federal_holidays(year: int) -> dict[date, str]:
    """The eleven US federal holidays (5 U.S.C. 6103) as observed in `year`."""
    holidays = {
        _observed(date(year, 1, 1)): "New Year's Day",
        _nth_weekday(year, 1, MONDAY, 3): "Birthday of Martin Luther King, Jr.",
        _nth_weekday(year, 2, MONDAY, 3): "Washington's Birthday",
        _last_weekday(year, 5, MONDAY): "Memorial Day",
        _observed(date(year, 6, 19)): "Juneteenth National Independence Day",
        _observed(date(year, 7, 4)): "Independence Day",
        _nth_weekday(year, 9, MONDAY, 1): "Labor Day",
        _nth_weekday(year, 10, MONDAY, 2): "Columbus Day",
        _observed(date(year, 11, 11)): "Veterans Day",
        _nth_weekday(year, 11, THURSDAY, 4): "Thanksgiving Day",
        _observed(date(year, 12, 25)): "Christmas Day",
    }
    # New Year's Day of next year observed on Dec 31 of this year (when Jan 1 is a Saturday)
    next_new_year = _observed(date(year + 1, 1, 1))
    if next_new_year.year == year:
        holidays[next_new_year] = "New Year's Day (observed)"
    return holidays


def is_business_day(day: date) -> bool:
    return day.weekday() < SATURDAY and day not in federal_holidays(day.year)


def add_business_days(start: date, count: int) -> date:
    """The date `count` business days after `start` (before it when `count` is negative). `start` itself is
    day 0 whether or not it is a business day, so a dispute reported on a Saturday gets the same deadline as
    one reported the Friday before."""
    step = timedelta(days=1 if count >= 0 else -1)
    day, remaining = start, abs(count)
    while remaining > 0:
        day += step
        if is_business_day(day):
            remaining -= 1
    return day


def business_days_between(start: date, end: date) -> int:
    """Business days in (start, end]; negative when `end` is before `start` (counts (end, start])."""
    if end < start:
        return -business_days_between(end, start)
    count, day = 0, start
    while day < end:
        day += timedelta(days=1)
        count += is_business_day(day)
    return count


def deadline_for(reported_on: str | None) -> str | None:
    """The Reg E deadline for a dispute reported on `reported_on`; goodwill refunds (None) have none."""
    if reported_on is None:
        return None
    return add_business_days(date.fromisoformat(reported_on), REG_E_BUSINESS_DAYS).isoformat()


def business_days_left(deadline_on: str | None, as_of: date | None = None) -> int | None:
    """Business days from `as_of` (default today) to the deadline: 0 means due today, negative means overdue
    by that many business days, None means no deadline."""
    if deadline_on is None:
        return None
    return business_days_between(as_of or today(), date.fromisoformat(deadline_on))
