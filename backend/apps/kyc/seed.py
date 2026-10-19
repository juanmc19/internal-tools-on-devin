"""Deterministic synthetic KYC data: 50,000 cases over 6 countries, 5 personas.

Audit history (see README): ~200 decided cases get a full chained history (claim, recommend, decide); every
other case is covered by one `seed.import` entry per 1,000 cases. All data is fictional; ids start with TEST-.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import insert
from sqlalchemy.orm import Session

from backend.apps.kyc.models import COUNTRIES, Case
from backend.platform import audit
from backend.platform.auth import RoleAssignment, upsert_user

CASE_COUNT = 50_000
FULL_HISTORY_COUNT = 200
IMPORT_BATCH = 1_000
SEED = 20261019

PERSONAS = [
    ("TEST-USR-ANA", "Ana Ruiz", "analyst", {"countries": ["MX", "CO"]}),
    ("TEST-USR-BRUNO", "Bruno Lima", "analyst", {"countries": ["BR", "AR"]}),
    ("TEST-USR-CAMILA", "Camila Torres", "senior_reviewer", {}),
    ("TEST-USR-DIEGO", "Diego Marín", "senior_reviewer", {}),
    ("TEST-USR-ELENA", "Elena Vega", "auditor", {}),
]
REVIEWERS = ["TEST-USR-CAMILA", "TEST-USR-DIEGO"]
ANALYSTS = {"MX": "TEST-USR-ANA", "CO": "TEST-USR-ANA", "BR": "TEST-USR-BRUNO", "AR": "TEST-USR-BRUNO"}

FIRST_NAMES = [
    "Ana",
    "Bruno",
    "Camila",
    "Diego",
    "Elena",
    "Felipe",
    "Gabriela",
    "Hugo",
    "Inés",
    "Javier",
    "Karla",
    "Luis",
    "Mariana",
    "Nicolás",
    "Olivia",
    "Pablo",
    "Quima",
    "Rafael",
    "Sofía",
    "Tomás",
    "Úrsula",
    "Valentina",
    "Wilson",
    "Ximena",
    "Yago",
    "Zoe",
]
LAST_NAMES = [
    "Alvarez",
    "Barros",
    "Castro",
    "Duarte",
    "Espinoza",
    "Fernández",
    "Gómez",
    "Herrera",
    "Ibarra",
    "Jiménez",
    "Klein",
    "López",
    "Mendoza",
    "Navarro",
    "Ortega",
    "Pereira",
    "Quintero",
    "Rojas",
    "Santos",
    "Torres",
    "Uribe",
    "Vargas",
    "Wong",
    "Ynez",
    "Zapata",
]
STREETS = [
    "Av. Reforma",
    "Calle Luna",
    "Rua das Flores",
    "Av. Libertador",
    "Calle Sol",
    "Jr. Unión",
    "Carrera 7",
]
CITIES = {
    "MX": ["Ciudad de México", "Guadalajara", "Monterrey"],
    "CO": ["Bogotá", "Medellín", "Cali"],
    "BR": ["São Paulo", "Rio de Janeiro", "Belo Horizonte"],
    "AR": ["Buenos Aires", "Córdoba", "Rosario"],
    "CL": ["Santiago", "Valparaíso", "Concepción"],
    "PE": ["Lima", "Arequipa", "Cusco"],
}
NOTES = [
    "Documents consistent with application; screening reviewed.",
    "Address proof older than 90 days; requested a new one.",
    "Possible match reviewed: different date of birth, false positive.",
    "ID number fails checksum; recommending rejection.",
    "Sanctions list match confirmed with secondary identifiers.",
]

STATUS_WEIGHTS = [("new", 55), ("in_review", 14), ("recommended", 10), ("approved", 16), ("rejected", 5)]
RISK_WEIGHTS = [("low", 62), ("medium", 28), ("high", 10)]
SCREENING_WEIGHTS = [("clear", 86), ("possible_match", 11), ("match", 3)]


def _weighted(rng: random.Random, pairs: list[tuple[str, int]]) -> str:
    return rng.choices([p[0] for p in pairs], weights=[p[1] for p in pairs], k=1)[0]


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def seed(session: Session) -> None:
    rng = random.Random(SEED)
    for uid, name, role, attrs in PERSONAS:
        upsert_user(
            session, id=uid, name=name, roles=[RoleAssignment(app="kyc", role=role, attributes=attrs)]
        )

    base = datetime(2026, 10, 1, tzinfo=UTC)
    history_ids: list[int] = []
    rows: list[dict] = []
    for i in range(1, CASE_COUNT + 1):
        country = COUNTRIES[(i - 1) % len(COUNTRIES)] if i <= 600 else rng.choice(COUNTRIES)
        status = _weighted(rng, STATUS_WEIGHTS)
        created = base - timedelta(minutes=rng.randint(0, 60 * 24 * 90))
        updated = created
        row = {
            "id": i,
            "reference": f"TEST-KYC-{i:06d}",
            "applicant_name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            "date_of_birth": (datetime(1950, 1, 1) + timedelta(days=rng.randint(0, 365 * 55))).strftime(
                "%Y-%m-%d"
            ),
            "id_number": f"{country}{rng.randint(10**8, 10**9 - 1)}",
            "address": f"{rng.randint(1, 999)} {rng.choice(STREETS)}, {rng.choice(CITIES[country])}",
            "country": country,
            "risk": _weighted(rng, RISK_WEIGHTS),
            "screening_result": _weighted(rng, SCREENING_WEIGHTS),
            "status": status,
            "assignee_id": None,
            "recommender_id": None,
            "recommendation": None,
            "recommendation_note": None,
            "decider_id": None,
            "decision": None,
            "created_at": _iso(created),
            "claimed_at": None,
            "recommended_at": None,
            "decided_at": None,
            "version": 1,
        }
        row["city"] = row["address"].rsplit(", ", 1)[1]
        if status != "new":
            claimer = ANALYSTS.get(country) or rng.choice(REVIEWERS)
            if rng.random() < 0.3:
                claimer = rng.choice(REVIEWERS)
            updated = created + timedelta(minutes=rng.randint(10, 60 * 24 * 3))
            row.update(assignee_id=claimer, claimed_at=_iso(updated), version=2)
        if status in ("recommended", "approved", "rejected"):
            updated += timedelta(minutes=rng.randint(10, 60 * 24 * 2))
            outcome = "reject" if row["screening_result"] == "match" or rng.random() < 0.15 else "approve"
            row.update(
                recommender_id=row["assignee_id"],
                recommendation=outcome,
                recommendation_note=rng.choice(NOTES),
                recommended_at=_iso(updated),
                version=3,
            )
        if status in ("approved", "rejected"):
            updated += timedelta(minutes=rng.randint(10, 60 * 24 * 2))
            decider = next(r for r in rng.sample(REVIEWERS, 2) if r != row["recommender_id"])
            row.update(
                decider_id=decider,
                decision="approve" if status == "approved" else "reject",
                decided_at=_iso(updated),
                version=4,
            )
            if len(history_ids) < FULL_HISTORY_COUNT:
                history_ids.append(i)
        row["updated_at"] = _iso(updated)
        rows.append(row)
        if len(rows) == 2_000:
            session.execute(insert(Case), rows)
            rows = []
    if rows:
        session.execute(insert(Case), rows)

    history = set(history_ids)
    for start in range(1, CASE_COUNT + 1, IMPORT_BATCH):
        end = min(start + IMPORT_BATCH - 1, CASE_COUNT)
        audit.write(
            session,
            app="kyc",
            actor_id=None,
            action="seed.import",
            record_type="case",
            record_id=f"TEST-KYC-{start:06d}..TEST-KYC-{end:06d}",
            diff={"count": end - start + 1, "full_history": sum(1 for i in history if start <= i <= end)},
            ts=_iso(base),
        )

    for case in session.query(Case).filter(Case.id.in_(history_ids)).order_by(Case.id):
        _write_history(session, case)
    session.flush()


def _write_history(session: Session, case: Case) -> None:
    common = {"app": "kyc", "record_type": "case", "record_id": case.reference}
    audit.write(
        session,
        actor_id=case.assignee_id,
        action="case.claim",
        diff={
            "status": {"from": "new", "to": "in_review"},
            "assignee_id": {"from": None, "to": case.assignee_id},
        },
        ts=case.claimed_at,
        **common,
    )
    audit.write(
        session,
        actor_id=case.recommender_id,
        action="case.recommend",
        diff={
            "status": {"from": "in_review", "to": "recommended"},
            "recommendation": {"from": None, "to": case.recommendation},
            "recommendation_note": {"changed": True},
        },
        ts=case.recommended_at,
        **common,
    )
    audit.write(
        session,
        actor_id=case.decider_id,
        action="case.decide",
        diff={
            "status": {"from": "recommended", "to": case.status},
            "decision": {"from": None, "to": case.decision},
        },
        ts=case.decided_at,
        **common,
    )
