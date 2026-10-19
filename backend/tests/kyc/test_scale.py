"""SCL-1 and SCL-2 against the real 50,000-case seed; SCL-3 is `make bench`."""

from __future__ import annotations

from backend.tests.kyc.conftest import ANA, CAMILA, as_user


def test_scl1_exact_totals_for_any_filter(big_client):
    page = big_client.get("/kyc/cases?page_size=50", headers=as_user(CAMILA)).json()
    assert page["total"] == 50_000 and len(page["items"]) == 50 and page["page"] == 1
    new = big_client.get("/kyc/cases?status=new&page_size=1", headers=as_user(CAMILA)).json()["total"]
    not_new = big_client.get("/kyc/cases/count?status=in_review", headers=as_user(CAMILA)).json()["count"]
    for status in ("recommended", "approved", "rejected"):
        not_new += big_client.get(f"/kyc/cases/count?status={status}", headers=as_user(CAMILA)).json()[
            "count"
        ]
    assert new + not_new == 50_000
    mx = big_client.get("/kyc/cases/count?country=MX", headers=as_user(CAMILA)).json()["count"]
    co = big_client.get("/kyc/cases/count?country=CO", headers=as_user(CAMILA)).json()["count"]
    assert big_client.get("/kyc/cases", headers=as_user(ANA)).json()["total"] == mx + co
    assert big_client.get("/kyc/cases?country=BR", headers=as_user(ANA)).json()["total"] == 0
    high = big_client.get("/kyc/cases?risk=high&screening_result=match", headers=as_user(CAMILA)).json()
    assert 0 < high["total"] < 50_000 and all(
        r["risk"] == "high" and r["screening_result"] == "match" for r in high["items"]
    )
    search = big_client.get("/kyc/cases?q=TEST-KYC-0123", headers=as_user(CAMILA)).json()
    assert search["total"] == 100 and all(r["reference"].startswith("TEST-KYC-0123") for r in search["items"])
    digits = big_client.get("/kyc/cases?q=4521", headers=as_user(CAMILA)).json()
    assert digits["total"] == 1 and digits["items"][0]["reference"] == "TEST-KYC-004521"


def test_scl2_walking_every_page_returns_every_case_once(big_client):
    seen: list[str] = []
    total = None
    page = 1
    while True:
        body = big_client.get(
            f"/kyc/cases?page={page}&page_size=200&sort=status&order=asc", headers=as_user(ANA)
        ).json()
        total = body["total"]
        seen.extend(row["reference"] for row in body["items"])
        if len(body["items"]) < 200:
            break
        page += 1
    assert len(seen) == total
    assert len(set(seen)) == total
    assert (
        big_client.get("/kyc/cases?sort=applicant_name", headers=as_user(ANA)).json()["code"]
        == "INVALID_SORT"
    )
    assert big_client.get("/kyc/cases?page_size=201", headers=as_user(ANA)).status_code == 422


def test_seed_history_strategy(big_client):
    """~200 cases carry a full chained history; the rest are covered by one seed.import entry per 1,000."""
    imports = big_client.get(
        "/audit?app=kyc&action=seed.import&page_size=200", headers=as_user(CAMILA)
    ).json()
    assert imports["total"] == 50
    assert sum(e["diff"]["count"] for e in imports["items"]) == 50_000
    decides = big_client.get("/audit?app=kyc&action=case.decide&page_size=1", headers=as_user(CAMILA)).json()
    assert decides["total"] == 200
    assert big_client.get("/audit/verify?app=kyc", headers=as_user(CAMILA)).json()["ok"] is True
    users = big_client.get("/dev/users").json()["items"]
    assert len(users) == 5
    ana = next(u for u in users if u["id"] == ANA)
    assert ana["roles"][0]["scope"] == ["MX", "CO"]
