"""FND-1: sign-in fails closed."""

from backend.tests.conftest import as_user


def test_fnd1_without_dev_env_every_authenticated_endpoint_is_401(prod_client):
    for path in ["/me", "/dev/users", "/testapp/widgets", "/testapp/widgets/1", "/audit?app=testapp"]:
        response = prod_client.get(path, headers=as_user("manager_1"))
        assert response.status_code == 401, path
        assert response.json()["code"] == "AUTH_REQUIRED"
    response = prod_client.post("/testapp/widgets/1/approve", headers=as_user("manager_1"))
    assert response.status_code == 401
    # health stays public so the Home page can show status
    assert prod_client.get("/health").status_code == 200


def test_fnd1_missing_header_is_401(client):
    response = client.get("/me")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_fnd1_unknown_user_is_401(client):
    response = client.get("/me", headers=as_user("nobody"))
    assert response.status_code == 401
    assert response.json()["code"] == "UNKNOWN_USER"


def test_fnd1_unknown_role_is_refused_on_every_route(client):
    for path in ["/testapp/widgets", "/testapp/widgets/1", "/testapp/widgets/count"]:
        response = client.get(path, headers=as_user("ghost"))
        assert response.status_code == 403, path
        assert response.json()["code"] == "UNKNOWN_ROLE"


def test_me_and_dev_users_describe_personas(client):
    me = client.get("/me", headers=as_user("viewer_north")).json()
    assert me["id"] == "viewer_north"
    role = me["roles"][0]
    assert role == {
        "app": "testapp",
        "app_name": "Test App",
        "role": "viewer",
        "role_label": "Viewer",
        "permissions": ["widget.read"],
        "masked": True,
        "scope": ["north"],
    }
    users = client.get("/dev/users").json()["items"]
    assert {u["id"] for u in users} == {
        "viewer_north",
        "viewer_none",
        "requester",
        "manager_1",
        "manager_2",
        "ghost",
    }
    manager = next(u for u in users if u["id"] == "manager_1")
    assert manager["roles"][0]["scope"] == ["All"]
    assert manager["roles"][0]["masked"] is False
