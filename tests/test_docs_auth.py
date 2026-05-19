# tests/test_docs_auth.py
import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.core.config import Settings
from app.main import app


def test_settings_has_docs_credentials():
    s = Settings(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        supabase_url="https://x.supabase.co",
        supabase_anon_key="anon-key",
        docs_username="admin",
        docs_password="secret",
    )
    assert s.docs_username == "admin"
    assert s.docs_password == "secret"


def test_settings_docs_credentials_have_defaults():
    s = Settings(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        supabase_url="https://x.supabase.co",
        supabase_anon_key="anon-key",
    )
    assert s.docs_username == "admin"
    assert s.docs_password == "changeme"


def test_settings_docs_credentials_from_env_vars(monkeypatch):
    monkeypatch.setenv("DOCS_USERNAME", "prod_user")
    monkeypatch.setenv("DOCS_PASSWORD", "prod_pass")
    s = Settings(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        supabase_url="https://x.supabase.co",
        supabase_anon_key="anon-key",
    )
    assert s.docs_username == "prod_user"
    assert s.docs_password == "prod_pass"


@pytest.fixture
async def docs_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _mock_settings(username: str = "admin", password: str = "secret"):
    m = MagicMock()
    m.docs_username = username
    m.docs_password = password
    return m


async def test_docs_without_auth_returns_401(docs_client):
    response = await docs_client.get("/docs")
    assert response.status_code == 401


async def test_docs_with_wrong_password_returns_401(docs_client):
    with patch("app.main.settings", _mock_settings()):
        response = await docs_client.get("/docs", auth=("admin", "wrong"))
    assert response.status_code == 401


async def test_docs_with_correct_auth_returns_200(docs_client):
    with patch("app.main.settings", _mock_settings()):
        response = await docs_client.get("/docs", auth=("admin", "secret"))
    assert response.status_code == 200


async def test_redoc_without_auth_returns_401(docs_client):
    response = await docs_client.get("/redoc")
    assert response.status_code == 401


async def test_redoc_with_correct_auth_returns_200(docs_client):
    with patch("app.main.settings", _mock_settings()):
        response = await docs_client.get("/redoc", auth=("admin", "secret"))
    assert response.status_code == 200
