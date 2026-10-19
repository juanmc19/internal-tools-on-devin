"""Server-side paging with allowlisted sorting and exact totals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.platform.errors import ApiError

MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class PageParams:
    page: int = 1
    page_size: int = 50
    sort: str | None = None
    order: str = "asc"


def page_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    sort: str | None = Query(None),
    order: str = Query("asc", pattern="^(asc|desc)$"),
) -> PageParams:
    return PageParams(page=page, page_size=page_size, sort=sort, order=order)


@dataclass
class Page:
    items: list[Any]
    total: int
    page: int
    page_size: int

    def to_dict(self, serialize) -> dict[str, Any]:
        return {
            "items": [serialize(item) for item in self.items],
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
        }


def paginate(
    session: Session,
    stmt: Select,
    params: PageParams,
    *,
    sort_columns: dict[str, Any],
    default_sort: str,
    tiebreaker: Any,
) -> Page:
    """Applies allowlisted sorting and offset paging to `stmt` and returns items plus the exact total.

    `tiebreaker` (normally the primary key) is always appended so that walking every page returns every
    row exactly once, even when the sort column has duplicates.
    """
    sort_key = params.sort or default_sort
    if sort_key not in sort_columns:
        raise ApiError(400, "INVALID_SORT", f"Cannot sort by '{sort_key}'.")
    column = sort_columns[sort_key]
    ordering = column.desc() if params.order == "desc" else column.asc()
    tiebreak = tiebreaker.desc() if params.order == "desc" else tiebreaker.asc()

    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    offset = (params.page - 1) * params.page_size
    rows = session.scalars(stmt.order_by(ordering, tiebreak).offset(offset).limit(params.page_size)).all()
    return Page(items=list(rows), total=total, page=params.page, page_size=params.page_size)
