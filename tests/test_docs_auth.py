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
    assert isinstance(s.docs_username, str)
    assert isinstance(s.docs_password, str)
