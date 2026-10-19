"""Masking strategies, applied by the policy engine in serializers according to the caller's role."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime

MASK = "\u2022\u2022\u2022\u2022"


def initials(value: object) -> object:
    if value is None:
        return None
    parts = str(value).split()
    return " ".join(f"{p[0].upper()}." for p in parts if p) or MASK


def last4(value: object) -> object:
    if value is None:
        return None
    text = str(value)
    return f"{MASK}{text[-4:]}" if len(text) > 4 else MASK


def city_only(value: object) -> object:
    """Keeps the last comma-separated component of an address ("12 Elm St, Austin" -> "Austin")."""
    if value is None:
        return None
    parts = [p.strip() for p in str(value).split(",") if p.strip()]
    return parts[-1] if parts else MASK


def day_only(value: object) -> object:
    """Keeps only the day of the month of a date ("1987-04-12" -> "••••-••-12")."""
    if value is None:
        return None
    if isinstance(value, datetime | date):
        day = value.day
    else:
        text = str(value)[:10]
        try:
            day = date.fromisoformat(text).day
        except ValueError:
            return MASK
    return f"{MASK}-\u2022\u2022-{day:02d}"


STRATEGIES: dict[str, Callable[[object], object]] = {
    "initials": initials,
    "last4": last4,
    "city_only": city_only,
    "day_only": day_only,
}


def apply(strategy: str, value: object) -> object:
    try:
        fn = STRATEGIES[strategy]
    except KeyError as exc:
        raise ValueError(f"Unknown masking strategy: {strategy}") from exc
    return fn(value)
