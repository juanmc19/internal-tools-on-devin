"""Paging helper: exact totals, allowlisted sorting, every row exactly once."""

from backend.tests.conftest import as_user


def test_walking_every_page_returns_every_row_once(client):
    seen: list[str] = []
    page = 1
    while True:
        body = client.get(
            f"/testapp/widgets?page={page}&page_size=2&sort=amount", headers=as_user("manager_1")
        ).json()
        assert body["total"] == 5 and body["page"] == page and body["page_size"] == 2
        seen.extend(w["reference"] for w in body["items"])
        if page * 2 >= body["total"]:
            break
        page += 1
    assert sorted(seen) == sorted(set(seen)) and len(seen) == 5


def test_sort_is_allowlisted_and_ordered(client):
    assert client.get("/testapp/widgets?sort=owner_name", headers=as_user("manager_1")).status_code == 400
    assert (
        client.get("/testapp/widgets?sort=owner_name", headers=as_user("manager_1")).json()["code"]
        == "INVALID_SORT"
    )
    desc = client.get("/testapp/widgets?sort=amount&order=desc", headers=as_user("manager_1")).json()["items"]
    assert [w["amount"] for w in desc] == [5000, 2500, 500, 100, 20]
    assert client.get("/testapp/widgets?page_size=999", headers=as_user("manager_1")).status_code == 422
