"""Deterministic synthetic refunds: 20,000 across 4 regions, 6 personas.

Audit history (see README): ~300 paid refunds get a full chained history (request, approval(s), paid); every
other refund is covered by one `seed.import` entry per 1,000. All data is fictional; ids start with TEST-,
and only the last 4 digits of a card are ever generated or stored.

Closed refunds are dated around a fixed base date. Open refunds are dated relative to the day the seed runs so
the queue shows a realistic Reg E mix: a few open disputes overdue, some due in the next 1 to 2 business days,
most with time left.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import insert
from sqlalchemy.orm import Session

from backend.apps.kyc.seed import FIRST_NAMES, LAST_NAMES
from backend.apps.refunds import business_days
from backend.apps.refunds.models import OPEN_STATUSES, REGIONS, Refund, RefundApproval
from backend.platform import audit
from backend.platform.auth import RoleAssignment, upsert_user

REFUND_COUNT = 20_000
FULL_HISTORY_COUNT = 300
IMPORT_BATCH = 1_000
SEED = 20261020
TWO_APPROVALS_ABOVE_CENTS = 500_000

PERSONAS = [
    ("TEST-USR-GABRIELA", "Gabriela Soto", "agent", {"regions": ["northeast", "southeast"]}),
    ("TEST-USR-HUGO", "Hugo Pérez", "agent", {"regions": ["midwest", "west"]}),
    ("TEST-USR-INES", "Inés Castillo", "approver", {}),
    ("TEST-USR-JAVIER", "Javier Ortiz", "approver", {}),
    ("TEST-USR-KARLA", "Karla Núñez", "finance", {}),
    ("TEST-USR-ELENA", "Elena Vega", "auditor", {}),  # also the KYC auditor: one person, roles in both apps
]
APPROVERS = ["TEST-USR-INES", "TEST-USR-JAVIER"]
FINANCE = "TEST-USR-KARLA"
AGENTS = {
    "northeast": "TEST-USR-GABRIELA",
    "southeast": "TEST-USR-GABRIELA",
    "midwest": "TEST-USR-HUGO",
    "west": "TEST-USR-HUGO",
}

GOODWILL_REASONS = [
    "Late delivery; goodwill credit agreed with the customer.",
    "Duplicate charge on the same order.",
    "Service outage during the billing period.",
    "Price adjustment after a promotion was missed.",
    "Customer cancelled within the cooling-off period.",
]
DISPUTE_REASONS = [
    "Customer does not recognise the transaction.",
    "Card reported lost; charge made after the report.",
    "Merchant charged twice for one purchase.",
    "Goods not received; merchant unresponsive.",
    "Subscription charged after cancellation.",
]

# requested 42%, pending 4% (only above $5,000), approved 9%, paid 35%, rejected 10%
STATUS_WEIGHTS = [
    ("requested", 42),
    ("pending_second_approval", 4),
    ("approved", 9),
    ("paid", 35),
    ("rejected", 10),
]

# open disputes by business days since the customer reported them: 11-15 is overdue, 8-10 is due within
# 2 business days (10 is due today), 0-7 has time left
OPEN_DISPUTE_AGE = [((11, 15), 5), ((8, 10), 12), ((0, 7), 83)]


def _weighted(rng: random.Random, pairs: list[tuple[str, int]]) -> str:
    return rng.choices([p[0] for p in pairs], weights=[p[1] for p in pairs], k=1)[0]


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _open_dates(rng: random.Random, now: datetime, is_dispute: bool) -> tuple[datetime, str | None]:
    """When an open refund was created and, for disputes, when the customer reported it, relative to `now`."""
    if not is_dispute:
        return now - timedelta(minutes=rng.randint(60, 60 * 24 * 21)), None
    low, high = _weighted(rng, OPEN_DISPUTE_AGE)
    reported = business_days.add_business_days(now.date(), -rng.randint(low, high))
    created = datetime.combine(reported, time(9, tzinfo=UTC)) + timedelta(minutes=rng.randint(0, 60 * 30))
    return min(created, now), reported.isoformat()


def _amount_cents(rng: random.Random) -> int:
    """Most refunds are small (median about $90); about 6% are large and some of those exceed $5,000."""
    if rng.random() < 0.92:
        return max(100, min(100_000, int(rng.lognormvariate(math.log(9_000), 0.9))))
    return rng.randint(100_000, 2_500_000)


def seed(session: Session, now: datetime | None = None) -> None:
    now = (now or datetime.now(UTC)).replace(microsecond=0)
    rng = random.Random(SEED)
    for uid, name, role, attrs in PERSONAS:
        upsert_user(
            session, id=uid, name=name, roles=[RoleAssignment(app="refunds", role=role, attributes=attrs)]
        )

    base = datetime(2026, 10, 1, tzinfo=UTC)
    history_ids: list[int] = []
    rows: list[dict] = []
    approvals: list[dict] = []
    for i in range(1, REFUND_COUNT + 1):
        region = REGIONS[(i - 1) % len(REGIONS)] if i <= 400 else rng.choice(REGIONS)
        amount = _amount_cents(rng)
        needs_two = amount > TWO_APPROVALS_ABOVE_CENTS
        status = _weighted(rng, STATUS_WEIGHTS)
        if status == "pending_second_approval" and not needs_two:
            status = "requested"
        is_dispute = rng.random() < 0.34
        requester = AGENTS[region] if rng.random() < 0.8 else rng.choice(APPROVERS)
        approvers = [a for a in APPROVERS if a != requester]
        if status in ("approved", "paid") and needs_two and len(approvers) < 2:
            # an approver requested a large refund: the other approver signs once, the rest stays pending
            status = "pending_second_approval"
        if status in OPEN_STATUSES:
            created, reported_on = _open_dates(rng, now, is_dispute)
        else:
            created = base - timedelta(minutes=rng.randint(0, 60 * 24 * 90))
            reported_on = (
                (created - timedelta(days=rng.randint(0, 20))).strftime("%Y-%m-%d") if is_dispute else None
            )
        row = {
            "id": i,
            "reference": f"TEST-RFD-{i:06d}",
            "customer_name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            "card_last4": f"{rng.randint(0, 9999):04d}",
            "amount_cents": amount,
            "type": "dispute" if is_dispute else "goodwill",
            "reason": rng.choice(DISPUTE_REASONS if is_dispute else GOODWILL_REASONS),
            "reported_on": reported_on,
            "deadline_on": business_days.deadline_for(reported_on),
            "region": region,
            "status": status,
            "requester_id": requester,
            "rejecter_id": None,
            "created_at": _iso(created),
            "approved_at": None,
            "paid_at": None,
            "rejected_at": None,
            "version": 1,
        }
        updated = created
        if status in ("pending_second_approval", "approved", "paid"):
            count = 1 if status == "pending_second_approval" else (2 if needs_two else 1)
            for approver in rng.sample(approvers, count):
                updated = min(updated + timedelta(minutes=rng.randint(10, 60 * 24 * 2)), now)
                approvals.append({"refund_id": i, "approver_id": approver, "approved_at": _iso(updated)})
                row["version"] += 1
            if status != "pending_second_approval":
                row["approved_at"] = _iso(updated)
        if status == "paid":
            updated += timedelta(minutes=rng.randint(10, 60 * 24 * 3))
            row["paid_at"] = _iso(updated)
            row["version"] += 1
            if len(history_ids) < FULL_HISTORY_COUNT:
                history_ids.append(i)
        if status == "rejected":
            updated += timedelta(minutes=rng.randint(10, 60 * 24 * 2))
            row.update(
                rejecter_id=rng.choice([a for a in APPROVERS if a != requester] or APPROVERS),
                rejected_at=_iso(updated),
                version=2,
            )
        row["updated_at"] = _iso(updated)
        rows.append(row)
        if len(rows) == 2_000:
            session.execute(insert(Refund), rows)
            rows = []
    if rows:
        session.execute(insert(Refund), rows)
    for start in range(0, len(approvals), 2_000):
        session.execute(insert(RefundApproval), approvals[start : start + 2_000])

    history = set(history_ids)
    for start in range(1, REFUND_COUNT + 1, IMPORT_BATCH):
        end = min(start + IMPORT_BATCH - 1, REFUND_COUNT)
        audit.write(
            session,
            app="refunds",
            actor_id=None,
            action="seed.import",
            record_type="refund",
            record_id=f"TEST-RFD-{start:06d}..TEST-RFD-{end:06d}",
            diff={"count": end - start + 1, "full_history": sum(1 for i in history if start <= i <= end)},
            ts=_iso(base),
        )

    for refund in session.query(Refund).filter(Refund.id.in_(history_ids)).order_by(Refund.id):
        _write_history(session, refund)
    session.flush()


def _write_history(session: Session, refund: Refund) -> None:
    common = {"app": "refunds", "record_type": "refund", "record_id": refund.reference}
    required = 2 if refund.amount_cents > TWO_APPROVALS_ABOVE_CENTS else 1
    audit.write(
        session,
        actor_id=refund.requester_id,
        action="refund.request",
        diff={
            "status": {"from": None, "to": "requested"},
            "amount_cents": {"from": None, "to": refund.amount_cents},
            "type": {"from": None, "to": refund.type},
            "region": {"from": None, "to": refund.region},
            "customer_name": {"changed": True},
            "card_last4": {"changed": True},
            "reason": {"changed": True},
        },
        ts=refund.created_at,
        **common,
    )
    status = "requested"
    for n, approval in enumerate(refund.approvals, start=1):
        after = "approved" if n >= required else "pending_second_approval"
        audit.write(
            session,
            actor_id=approval.approver_id,
            action="refund.approve",
            diff={"status": {"from": status, "to": after}, "approvals": f"{n} of {required}"},
            ts=approval.approved_at,
            **common,
        )
        status = after
    audit.write(
        session,
        actor_id=FINANCE,
        action="refund.pay",
        diff={"status": {"from": "approved", "to": "paid"}, "amount_cents": refund.amount_cents},
        ts=refund.paid_at,
        **common,
    )
