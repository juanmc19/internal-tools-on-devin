"""Deterministic synthetic refunds: 20,000 across 4 regions, 6 personas.

Audit history (see README): ~300 paid refunds get a full chained history (request, approval(s), paid); every
other refund is covered by one `seed.import` entry per 1,000. All data is fictional; ids start with TEST-,
and only the last 4 digits of a card are ever generated or stored.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import insert
from sqlalchemy.orm import Session

from backend.apps.kyc.seed import FIRST_NAMES, LAST_NAMES
from backend.apps.refunds.models import REGIONS, Refund, RefundApproval
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


def _weighted(rng: random.Random, pairs: list[tuple[str, int]]) -> str:
    return rng.choices([p[0] for p in pairs], weights=[p[1] for p in pairs], k=1)[0]


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _amount_cents(rng: random.Random) -> int:
    """Most refunds are small (median about $90); about 6% are large and some of those exceed $5,000."""
    if rng.random() < 0.92:
        return max(100, min(100_000, int(rng.lognormvariate(math.log(9_000), 0.9))))
    return rng.randint(100_000, 2_500_000)


def seed(session: Session) -> None:
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
        created = base - timedelta(minutes=rng.randint(0, 60 * 24 * 90))
        requester = AGENTS[region] if rng.random() < 0.8 else rng.choice(APPROVERS)
        row = {
            "id": i,
            "reference": f"TEST-RFD-{i:06d}",
            "customer_name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            "card_last4": f"{rng.randint(0, 9999):04d}",
            "amount_cents": amount,
            "type": "dispute" if is_dispute else "goodwill",
            "reason": rng.choice(DISPUTE_REASONS if is_dispute else GOODWILL_REASONS),
            "reported_on": (created - timedelta(days=rng.randint(0, 20))).strftime("%Y-%m-%d")
            if is_dispute
            else None,
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
            approvers = [a for a in APPROVERS if a != requester]
            if len(approvers) < 2 and needs_two and status != "pending_second_approval":
                # an approver requested a large refund: the other approver signs once, the rest stays pending
                status = row["status"] = "pending_second_approval"
            count = 1 if status == "pending_second_approval" else (2 if needs_two else 1)
            for approver in rng.sample(approvers, count):
                updated += timedelta(minutes=rng.randint(10, 60 * 24 * 2))
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
