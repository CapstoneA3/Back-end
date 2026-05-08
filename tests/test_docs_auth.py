# tests/test_docs_auth.py
import pytest
from app.core.config import Settings


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
