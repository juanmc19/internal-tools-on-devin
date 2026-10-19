"""TLR-1 to TLR-3: the Reg E deadline (10 business days from the customer's report) on every dispute, the
queue sorted by it on the server, overdue disputes flagged, goodwill refunds without a deadline. "Today" is
fixed by monkeypatching `business_days.today`."""

from __future__ import annotations

import random
import time
from datetime import date, timedelta

import pytest

from backend.apps.refunds import business_days
from backend.apps.refunds.business_days import (
    add_business_days,
    business_days_between,
    deadline_for,
    federal_holidays,
    is_business_day,
)
from backend.tests.refunds.conftest import GABRIELA, INES, as_user

SMALL_NE = 1  # goodwill
LARGE_NE = 2  # dispute reported Sun 2026-09-20 -> deadline Fri 2026-10-02


@pytest.fixture
def today(monkeypatch):
    """Thursday 2026-10-01, the day before the seeded dispute's deadline."""
    fixed = date(2026, 10, 1)
    monkeypatch.setattr(business_days, "today", lambda: fixed)
    return fixed


def dispute(reported_on: str, amount: int = 10_000) -> dict:
    return {
        "customer_name": "Dee Sputes",
        "card_last4": "4242",
        "amount_cents": amount,
        "type": "dispute",
        "reason": "Customer does not recognise the transaction.",
        "reported_on": reported_on,
        "region": "northeast",
    }


# ---- TLR-1: business days, holidays in one place, the deadline stored on creation --------------------------


def test_tlr1_us_federal_holidays_are_computed_by_rule_with_observed_dates():
    assert {d.isoformat() for d in federal_holidays(2026)} == {
        "2026-01-01",  # New Year's Day
        "2026-01-19",  # MLK, 3rd Monday of January
        "2026-02-16",  # Washington's Birthday
        "2026-05-25",  # Memorial Day, last Monday of May
        "2026-06-19",  # Juneteenth
        "2026-07-03",  # Independence Day falls on a Saturday: observed Friday
        "2026-09-07",  # Labor Day
        "2026-10-12",  # Columbus Day
        "2026-11-11",  # Veterans Day
        "2026-11-26",  # Thanksgiving, 4th Thursday
        "2026-12-25",  # Christmas
    }
    # Christmas 2027 is a Saturday (observed Friday) and New Year's 2028 is a Saturday (observed 31 Dec 2027)
    assert date(2027, 12, 24) in federal_holidays(2027) and date(2027, 12, 31) in federal_holidays(2027)
    assert date(2028, 1, 1) not in federal_holidays(2028)  # already observed in 2027
    assert date(2028, 12, 25) in federal_holidays(2028)  # a Monday: not shifted


@pytest.mark.parametrize(
    ("reported_on", "deadline_on", "why"),
    [
        ("2026-09-16", "2026-09-30", "spans two weekends: Wed + 10 business days"),
        ("2026-09-18", "2026-10-02", "reported on a Friday"),
        ("2026-09-19", "2026-10-02", "reported on a Saturday counts like the Friday before"),
        ("2026-09-20", "2026-10-02", "reported on a Sunday counts like the Friday before"),
        ("2026-10-05", "2026-10-20", "spans Columbus Day (Mon 12 Oct): one day later than weekends alone"),
        ("2026-11-20", "2026-12-07", "spans Thanksgiving"),
        ("2026-07-01", "2026-07-16", "spans Independence Day observed on Friday 3 July"),
        ("2026-12-18", "2027-01-05", "spans Christmas and New Year's Day across the year boundary"),
    ],
)
def test_tlr1_deadline_is_10_business_days_after_the_report(reported_on, deadline_on, why):
    assert deadline_for(reported_on) == deadline_on, why
    assert add_business_days(date.fromisoformat(deadline_on), -10) <= date.fromisoformat(reported_on)


def test_tlr1_dispute_shows_business_days_left_and_stores_its_deadline(client, today):
    seeded = client.get(f"/refunds/{LARGE_NE}", headers=as_user(GABRIELA)).json()
    assert seeded["reported_on"] == "2026-09-20"
    assert seeded["deadline_on"] == "2026-10-02"
    assert seeded["business_days_left"] == 1  # Thursday: Friday is the last business day

    r = client.post("/refunds", json=dispute("2026-09-23"), headers=as_user(GABRIELA))
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["deadline_on"] == "2026-10-07"
    assert created["business_days_left"] == 4  # Fri 2, Mon 5, Tue 6, Wed 7
    history = client.get(f"/refunds/{created['id']}/history", headers=as_user(INES)).json()["items"]
    assert history[0]["diff"]["deadline_on"] == {"from": None, "to": "2026-10-07"}

    r = client.post("/refunds", json=dispute("2026-10-02"), headers=as_user(GABRIELA))
    assert r.status_code == 400 and r.json()["code"] == "REPORTED_ON_IN_FUTURE"


def test_tlr1_days_left_counts_down_to_zero_then_negative(client, monkeypatch):
    for as_of, left in (
        (date(2026, 10, 2), 0),
        (date(2026, 10, 3), -0),
        (date(2026, 10, 5), -1),
        (date(2026, 10, 14), -7),
    ):
        monkeypatch.setattr(business_days, "today", lambda d=as_of: d)
        got = client.get(f"/refunds/{LARGE_NE}", headers=as_user(INES)).json()["business_days_left"]
        assert got == left, as_of  # 14 Oct: 5, 6, 7, 8, 9, (12 is Columbus Day), 13, 14 = 7 overdue


def _business_days_between_by_walking(start: date, end: date) -> int:
    if end < start:
        return -_business_days_between_by_walking(end, start)
    count, day = 0, start
    while day < end:
        day += timedelta(days=1)
        count += is_business_day(day)
    return count


def test_tlr1_business_days_between_matches_a_day_by_day_count():
    rng = random.Random(7)
    pairs = [(date(2026, 9, 20), date(2026, 10, 2)), (date(2027, 12, 23), date(2028, 1, 4))]
    # around the 400-year cycle boundaries the closed form relies on
    pairs += [(date(1999, 12, 24), date(2000, 1, 4)), (date(2399, 12, 24), date(2400, 1, 4))]
    for _ in range(300):
        start = date(1995, 1, 1) + timedelta(days=rng.randint(0, 365 * 12))
        pairs.append((start, start + timedelta(days=rng.randint(-400, 400))))
    for start, end in pairs:
        assert business_days_between(start, end) == _business_days_between_by_walking(start, end), (
            start,
            end,
        )


def test_tlr1_business_days_between_is_constant_time_for_any_gap():
    started = time.perf_counter()
    for _ in range(1_000):
        days = business_days_between(date(1, 1, 15), date(2026, 10, 1))
    assert time.perf_counter() - started < 0.5
    assert days == business_days_between(date(1, 1, 15), date(1626, 10, 1)) + business_days_between(
        date(1626, 10, 1), date(2026, 10, 1)
    )
    assert -days == business_days_between(date(2026, 10, 1), date(1, 1, 15))


@pytest.mark.parametrize(
    ("reported_on", "code"),
    [
        ("0001-01-01", "REPORTED_ON_TOO_OLD"),
        ("2024-09-30", "REPORTED_ON_TOO_OLD"),  # 731 days before 1 Oct 2026
        ("2026-02-30", "INVALID_REPORTED_ON"),
        ("2026-13-01", "INVALID_REPORTED_ON"),
    ],
)
def test_tlr1_report_date_must_be_a_real_date_within_two_years(client, today, reported_on, code):
    r = client.post("/refunds", json=dispute(reported_on), headers=as_user(GABRIELA))
    assert r.status_code == 400 and r.json()["code"] == code
    assert client.post("/refunds", json=dispute("2024-10-01"), headers=as_user(GABRIELA)).status_code == 201


# ---- TLR-2: sort by most urgent on the server, overdue flagged ---------------------------------------------


def test_tlr2_queue_sorts_by_deadline_most_urgent_first_and_pages_every_row_once(client, today):
    reported = ["2026-09-30", "2026-09-10", "2026-09-25", "2026-09-14", "2026-09-28", "2026-09-17"]
    for day in reported:
        assert client.post("/refunds", json=dispute(day), headers=as_user(GABRIELA)).status_code == 201
    expected = sorted(deadline_for(day) for day in reported + ["2026-09-20"] * 2)  # plus 2 seeded disputes

    page = client.get("/refunds?sort=deadline_on&order=asc&page_size=50", headers=as_user(INES)).json()
    deadlines = [r["deadline_on"] for r in page["items"]]
    disputes = [d for d in deadlines if d is not None]
    assert disputes == expected
    assert deadlines == disputes + [None] * (len(deadlines) - len(disputes)), "goodwill sorts last"
    overdue = [
        r for r in page["items"] if r["business_days_left"] is not None and r["business_days_left"] < 0
    ]
    assert [r["deadline_on"] for r in overdue] == ["2026-09-24", "2026-09-28"]  # 10 and 14 Sep reports
    assert all(r["type"] == "dispute" for r in overdue)

    desc = client.get("/refunds?sort=deadline_on&order=desc&page_size=50", headers=as_user(INES)).json()
    assert [r["deadline_on"] for r in desc["items"] if r["deadline_on"]] == list(reversed(expected))

    seen: list[int] = []
    for page_no in range(1, 20):
        chunk = client.get(
            f"/refunds?sort=deadline_on&order=asc&page={page_no}&page_size=3", headers=as_user(INES)
        ).json()
        seen += [r["id"] for r in chunk["items"]]
        if page_no * 3 >= chunk["total"]:
            break
    assert len(seen) == len(set(seen)) == page["total"]


def test_tlr2_seed_dates_open_disputes_relative_to_today(big_client):
    """A realistic mix: a few overdue, some due within 2 business days, most with time left."""
    left: list[int] = []
    page_no = 1
    while True:
        page = big_client.get(
            f"/refunds?status=requested,pending_second_approval&type=dispute&sort=deadline_on"
            f"&page={page_no}&page_size=200",
            headers=as_user(INES),
        ).json()
        left += [r["business_days_left"] for r in page["items"]]
        if page_no * 200 >= page["total"]:
            break
        page_no += 1
    total = len(left)
    assert total > 1_000 and all(isinstance(n, int) for n in left)
    overdue = sum(n < 0 for n in left) / total
    due_soon = sum(0 <= n <= 2 for n in left) / total
    time_left = sum(n > 2 for n in left) / total
    assert 0.02 <= overdue <= 0.08, overdue
    assert (
        min(left) >= -6
    ), "nothing is overdue by weeks: open disputes are dated from today, not the base date"
    assert 0.06 <= due_soon <= 0.20, due_soon
    assert time_left >= 0.70, time_left
    assert left == sorted(left), "the queue sorted by deadline is sorted by days left"

    paid = big_client.get("/refunds?status=paid&type=dispute&page_size=5", headers=as_user(INES)).json()
    assert all(
        r["reported_on"] < "2026-10-01" and r["deadline_on"] for r in paid["items"]
    ), "closed stay as they were"


def test_tlr2_sort_is_allowlisted(client):
    r = client.get("/refunds?sort=business_days_left", headers=as_user(INES))
    assert r.status_code == 400 and r.json()["code"] == "INVALID_SORT"


# ---- TLR-3: goodwill refunds have no deadline --------------------------------------------------------------


def test_tlr3_goodwill_has_no_deadline(client, today):
    seeded = client.get(f"/refunds/{SMALL_NE}", headers=as_user(GABRIELA)).json()
    assert seeded["type"] == "goodwill"
    assert seeded["deadline_on"] is None and seeded["business_days_left"] is None

    body = {**dispute("2026-09-25"), "type": "goodwill"}  # a report date on a goodwill refund is ignored
    created = client.post("/refunds", json=body, headers=as_user(GABRIELA)).json()
    assert created["reported_on"] is None
    assert created["deadline_on"] is None and created["business_days_left"] is None
    for r in client.get("/refunds?type=goodwill&page_size=50", headers=as_user(INES)).json()["items"]:
        assert r["deadline_on"] is None and r["business_days_left"] is None
