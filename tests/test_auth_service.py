import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from app.services.auth_service import signup, login


def _make_auth_response(user_id="uuid-1234", email="test@example.com", token="tok"):
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


async def test_signup_success():
    mock_supabase = MagicMock()
    mock_supabase.auth.sign_up = AsyncMock(return_value=_make_auth_response())

    result = await signup(mock_supabase, "test@example.com", "password123")

    assert result["access_token"] == "tok"
    assert result["token_type"] == "bearer"
    assert result["user"]["id"] == "uuid-1234"
    assert result["user"]["email"] == "test@example.com"


async def test_signup_duplicate_email_raises_400():
    mock_supabase = MagicMock()
    mock_supabase.auth.sign_up = AsyncMock(side_effect=Exception("User already registered"))

    with pytest.raises(HTTPException) as exc:
        await signup(mock_supabase, "dup@example.com", "password123")

    assert exc.value.status_code == 400
    assert "already registered" in exc.value.detail


async def test_login_success():
    mock_supabase = MagicMock()
    mock_supabase.auth.sign_in_with_password = AsyncMock(
        return_value=_make_auth_response(token="login-tok")
    )

    result = await login(mock_supabase, "test@example.com", "password123")

    assert result["access_token"] == "login-tok"
    assert result["user"]["email"] == "test@example.com"


async def test_login_invalid_credentials_raises_401():
    mock_supabase = MagicMock()
    mock_supabase.auth.sign_in_with_password = AsyncMock(
        side_effect=Exception("Invalid login credentials")
    )

    with pytest.raises(HTTPException) as exc:
        await login(mock_supabase, "test@example.com", "wrongpass")

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid email or password"
