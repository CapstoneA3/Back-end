import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from app.main import app
from app.core.supabase_client import get_supabase


def _make_auth_response(user_id="uuid-1234", email="test@example.com", token="access-tok"):
    user = MagicMock()
    user.id = user_id
    user.email = email
    session = MagicMock()
    session.access_token = token
    session.token_type = "bearer"
    resp = MagicMock()
    resp.user = user
    resp.session = session
    return resp


def _make_user_response(user_id="uuid-1234", email="test@example.com"):
    user = MagicMock()
    user.id = user_id
    user.email = email
    user.created_at = "2026-05-06T00:00:00+00:00"
    resp = MagicMock()
    resp.user = user
    return resp


@pytest.fixture
async def mock_supabase():
    supabase = MagicMock()
    supabase.auth.sign_up = AsyncMock(return_value=_make_auth_response())
    supabase.auth.sign_in_with_password = AsyncMock(
        return_value=_make_auth_response(token="login-tok")
    )
    supabase.auth.get_user = AsyncMock(return_value=_make_user_response())
    return supabase


@pytest.fixture
async def auth_client(mock_supabase):
    async def override_get_supabase():
        return mock_supabase

    app.dependency_overrides[get_supabase] = override_get_supabase
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_signup_success(auth_client):
    resp = await auth_client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["access_token"] == "access-tok"
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["user"]["email"] == "test@example.com"
    assert body["message"] == "회원가입이 완료되었습니다."


async def test_signup_duplicate_email(auth_client, mock_supabase):
    mock_supabase.auth.sign_up = AsyncMock(side_effect=Exception("User already registered"))

    resp = await auth_client.post(
        "/api/v1/auth/signup",
        json={"email": "dup@example.com", "password": "password123"},
    )
    assert resp.status_code == 400


async def test_login_success(auth_client):
    resp = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["access_token"] == "login-tok"


async def test_login_invalid_credentials(auth_client, mock_supabase):
    mock_supabase.auth.sign_in_with_password = AsyncMock(
        side_effect=Exception("Invalid login credentials")
    )

    resp = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrongpass"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


async def test_me_success(auth_client):
    resp = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["id"] == "uuid-1234"
    assert body["data"]["email"] == "test@example.com"
    assert "created_at" in body["data"]


async def test_me_missing_authorization_header(auth_client):
    resp = await auth_client.get("/api/v1/auth/me")
    assert resp.status_code == 422


async def test_me_invalid_token(auth_client, mock_supabase):
    mock_supabase.auth.get_user = AsyncMock(side_effect=Exception("Invalid JWT"))

    resp = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer bad-token"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or expired token"
