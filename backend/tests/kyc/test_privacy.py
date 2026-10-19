"""PRIV-1, PRIV-2, PRIV-3: masking by role, row scope by country, unmasked reads."""

from __future__ import annotations

from backend.tests.kyc.conftest import ANA, BRUNO, CAMILA, ELENA, as_user

MX_CASE = 1  # Ana Ruiz, MX123456789, 12 Av. Reforma, Ciudad de México, 1987-04-12
BR_CASE = 4


def assert_masked(record: dict) -> None:
    assert record["applicant_name"] == "A. R."
    assert record["id_number"] == "••••6789"
    assert record["address"] == "••••"
    assert record["city"] == "Ciudad de México"
    assert record["date_of_birth"] == "••••-••-12"
    assert record["masked"] is True


def test_priv1_analyst_sees_masked_fields_in_list_and_detail(client):
    rows = client.get("/kyc/cases?q=TEST-KYC-000001", headers=as_user(ANA)).json()["items"]
    assert len(rows) == 1
    assert_masked(rows[0])
    assert_masked(client.get(f"/kyc/cases/{MX_CASE}", headers=as_user(ANA)).json())


def test_priv1_auditor_is_masked_and_queue_rows_are_masked_for_everyone(client):
    assert_masked(client.get(f"/kyc/cases/{MX_CASE}", headers=as_user(ELENA)).json())
    senior_rows = client.get("/kyc/cases?q=TEST-KYC-000001", headers=as_user(CAMILA)).json()["items"]
    assert_masked(senior_rows[0])


def test_priv1_no_full_pii_anywhere_in_an_analyst_page(client):
    body = client.get("/kyc/cases?page_size=200", headers=as_user(ANA)).text
    for secret in (
        "Ana Ruiz",
        "MX123456789",
        "Av. Reforma",
        "12 Av.",
        "1987-04-12",
        "Cy Diaz",
        "CO111222333",
    ):
        assert secret not in body


def test_priv2_analyst_scope_in_list_count_and_lookup(client):
    page = client.get("/kyc/cases", headers=as_user(ANA)).json()
    assert page["total"] == 3
    assert {row["country"] for row in page["items"]} == {"MX", "CO"}
    assert client.get("/kyc/cases/count", headers=as_user(ANA)).json() == {"count": 3}
    assert client.get("/kyc/cases?country=BR", headers=as_user(ANA)).json()["total"] == 0
    assert client.get("/kyc/cases/count?country=BR", headers=as_user(ANA)).json() == {"count": 0}
    assert client.get(f"/kyc/cases/{BR_CASE}", headers=as_user(ANA)).status_code == 404
    assert client.get(f"/kyc/cases/{BR_CASE}/history", headers=as_user(ANA)).status_code == 404
    assert client.get(f"/kyc/cases/{MX_CASE}", headers=as_user(BRUNO)).status_code == 404
    assert client.get("/kyc/cases", headers=as_user(CAMILA)).json()["total"] == 8


def test_priv2_out_of_scope_actions_are_404_not_403(client):
    r = client.post(f"/kyc/cases/{BR_CASE}/claim", json={"version": 1}, headers=as_user(ANA))
    assert r.status_code == 404


def test_priv3_analyst_unmasked_request_is_refused_and_recorded(client):
    r = client.get(f"/kyc/cases/{MX_CASE}?unmasked=true", headers=as_user(ANA))
    assert r.status_code == 403
    assert r.json()["code"] == "PII_MASKED_FOR_ROLE"
    entries = client.get("/audit?app=kyc&record_id=TEST-KYC-000001", headers=as_user(CAMILA)).json()["items"]
    denied = [e for e in entries if e["action"] == "security.denied"]
    assert denied and denied[0]["diff"]["code"] == "PII_MASKED_FOR_ROLE" and denied[0]["actor_id"] == ANA


def test_priv3_senior_unmasked_read_is_unmasked_and_audited(client):
    r = client.get(f"/kyc/cases/{MX_CASE}", headers=as_user(CAMILA))
    assert r.status_code == 200
    body = r.json()
    assert (
        body["applicant_name"] == "Ana Ruiz"
        and body["id_number"] == "MX123456789"
        and body["masked"] is False
    )
    history = client.get(f"/kyc/cases/{MX_CASE}/history", headers=as_user(CAMILA)).json()["items"]
    reads = [e for e in history if e["action"] == "case.read_unmasked"]
    assert len(reads) == 1 and reads[0]["actor_id"] == CAMILA
    assert "Ana Ruiz" not in str(reads[0]["diff"])
    client.get(f"/kyc/cases/{MX_CASE}", headers=as_user(CAMILA))
    history = client.get(f"/kyc/cases/{MX_CASE}/history", headers=as_user(CAMILA)).json()["items"]
    assert len([e for e in history if e["action"] == "case.read_unmasked"]) == 2


def test_priv3_masked_roles_do_not_write_unmasked_read_entries(client):
    client.get(f"/kyc/cases/{MX_CASE}", headers=as_user(ANA))
    client.get(f"/kyc/cases/{MX_CASE}", headers=as_user(ELENA))
    history = client.get(f"/kyc/cases/{MX_CASE}/history", headers=as_user(ANA)).json()["items"]
    assert not [e for e in history if e["action"] == "case.read_unmasked"]


def test_fnd1_kyc_endpoints_fail_closed(client, tmp_path):
    from fastapi.testclient import TestClient

    from backend.tests.kyc.conftest import build_app

    assert client.get("/kyc/cases").status_code == 401
    assert client.get("/kyc/cases", headers=as_user("TEST-USR-NOBODY")).status_code == 401
    r = client.get("/kyc/cases", headers=as_user("TEST-USR-GHOST"))
    assert r.status_code == 403 and r.json()["code"] == "UNKNOWN_ROLE"
    with TestClient(build_app(tmp_path / "prod.db", env="prod")) as prod:
        assert prod.get("/kyc/cases", headers=as_user(ANA)).status_code == 401


def test_analyst_history_shows_only_workflow_steps(client):
    client.get(f"/kyc/cases/{MX_CASE}", headers=as_user(CAMILA))
    client.get(f"/kyc/cases/{MX_CASE}?unmasked=true", headers=as_user(ANA))
    case = client.get(f"/kyc/cases/{MX_CASE}", headers=as_user(ANA)).json()
    client.post(f"/kyc/cases/{MX_CASE}/claim", json={"version": case["version"]}, headers=as_user(ANA))
    full = client.get(f"/kyc/cases/{MX_CASE}/history", headers=as_user(ELENA)).json()["items"]
    assert {"case.read_unmasked", "case.claim"} <= {e["action"] for e in full}
    assert all(e["hash"] and "request_id" in e for e in full)
    trimmed = client.get(f"/kyc/cases/{MX_CASE}/history", headers=as_user(ANA)).json()
    assert trimmed["total"] == len(trimmed["items"]) and trimmed["items"]
    assert {e["action"] for e in trimmed["items"]} <= {"case.claim", "case.recommend", "case.decide"}
    claim = next(e for e in trimmed["items"] if e["action"] == "case.claim")
    assert claim["actor_id"] == ANA and claim["diff"]["status"]["to"] == "in_review"
    assert not any({"request_id", "hash", "prev_hash"} & e.keys() for e in trimmed["items"])


def test_case_history_route_is_paged(client):
    for _ in range(3):
        client.get(f"/kyc/cases/{MX_CASE}?unmasked=true", headers=as_user(CAMILA))
    everything = client.get(f"/kyc/cases/{MX_CASE}/history", headers=as_user(ELENA)).json()
    assert everything["page"] == 1 and everything["page_size"] == 50
    total = everything["total"]
    assert total >= 3
    first = client.get(f"/kyc/cases/{MX_CASE}/history?page_size=2", headers=as_user(ELENA)).json()
    second = client.get(f"/kyc/cases/{MX_CASE}/history?page_size=2&page=2", headers=as_user(ELENA)).json()
    assert first["total"] == second["total"] == total and len(first["items"]) == 2
    assert [e["id"] for e in first["items"] + second["items"]] == [e["id"] for e in everything["items"][:4]]
    too_big = client.get(f"/kyc/cases/{MX_CASE}/history?page_size=201", headers=as_user(ELENA))
    assert too_big.status_code == 422
