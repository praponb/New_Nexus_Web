import pytest

from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_register_returns_user_and_tokens(api_client):
    res = api_client.post(
        "/api/v1/auth/register/",
        {"email": "New@Example.com", "password": PASSWORD, "full_name": "Alex Taylor"},
        format="json",
    )
    assert res.status_code == 201, res.content
    body = res.json()
    assert body["success"] is True
    assert body["data"]["user"]["email"] == "new@example.com"
    assert body["data"]["user"]["full_name"] == "Alex Taylor"
    assert set(body["data"]["tokens"]) == {"access", "refresh"}


def test_register_rejects_duplicate_and_weak_password(api_client, user):
    dup = api_client.post("/api/v1/auth/register/", {"email": user.email, "password": PASSWORD}, format="json")
    assert dup.status_code == 400
    assert dup.json()["success"] is False
    assert dup.json()["error"]["code"] == "validation_error"

    weak = api_client.post("/api/v1/auth/register/", {"email": "weak@example.com", "password": "123"}, format="json")
    assert weak.status_code == 400


def test_login_success_and_failure(api_client, user):
    res = api_client.post("/api/v1/auth/login/", {"email": "ALEX@example.com", "password": PASSWORD}, format="json")
    assert res.status_code == 200
    assert "access" in res.json()["data"]["tokens"]

    bad = api_client.post("/api/v1/auth/login/", {"email": user.email, "password": "wrong-password"}, format="json")
    assert bad.status_code == 401
    assert bad.json() == {
        "success": False,
        "error": {"code": "invalid_credentials", "message": "Invalid email or password."},
    }


def test_refresh_rotates_and_blacklists(api_client, user):
    tokens = api_client.post("/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json").json()[
        "data"
    ]["tokens"]
    res = api_client.post("/api/v1/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert res.status_code == 200
    assert "access" in res.json()["data"]
    # Old refresh token is blacklisted after rotation.
    again = api_client.post("/api/v1/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert again.status_code == 401
    assert again.json()["success"] is False


def test_me_requires_auth_and_returns_quota(api_client, auth_client):
    anon = api_client.get("/api/v1/auth/me/")
    assert anon.status_code == 401
    assert anon.json()["success"] is False

    res = auth_client.get("/api/v1/auth/me/")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["user"]["email"] == "alex@example.com"
    assert data["quota"]["projects_count"] == 0
    assert data["quota"]["remaining_generations"] == data["quota"]["monthly_generation_limit"]
