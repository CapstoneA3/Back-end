# load .env.local before app imports so Settings() picks up test DB credentials
from pathlib import Path
from dotenv import load_dotenv

_env_local = Path(__file__).parent.parent.parent.parent / ".env.local"
if _env_local.exists():
    load_dotenv(_env_local, override=True)

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.core.config import settings
from app.dependencies.auth import get_current_user_id

TEST_USER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def mock_db():
    """기존 테스트(test_inventory 등) 하위 호환용 AsyncMock."""
    return AsyncMock()


@pytest.fixture
async def db():
    """레시피 테스트용 실제 test DB 세션 (CI 환경에서는 건너뜀)."""
    import os
    if os.getenv("CI"):
        pytest.skip("CI 환경에서는 실제 DB 연결 테스트를 건너뜁니다.")
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
async def client(mock_db, mock_redis):
    """기존 테스트(test_inventory 등)용 — mock DB 사용."""
    async def override_get_db():
        yield mock_db

    async def override_get_current_user_id():
        return "user1"

    async def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
async def real_client(db, mock_redis):
    """레시피 라우터 테스트용 — 실제 test DB + mock Redis + 인증 오버라이드."""
    async def override_get_db():
        yield db

    async def override_get_current_user_id():
        return TEST_USER_ID

    async def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
