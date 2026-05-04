# 백엔드 서버 구조 + F-01/F-02 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FastAPI 백엔드 서버 초기 구조를 세우고, Supabase(PostgreSQL)와 Redis에 연결한 뒤 식재료 등록(F-01)과 재고 대시보드(F-02)를 구현한다.

**Architecture:** SQLAlchemy 2.0 async + asyncpg 로 Supabase PostgreSQL에 직접 연결하고, redis-py asyncio 로 BitSet을 캐싱한다. 라우터는 얇게 유지하고 비즈니스 로직은 `services/`에 집중시킨다. 인증 미확정 구간은 `X-User-ID` 헤더로 임시 처리하며 이후 교체 가능한 Depends 구조로 설계한다.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2.0 (asyncio), asyncpg 0.30, redis-py 5.x, Pydantic v2 + pydantic-settings, pytest 8, pytest-asyncio 0.24, httpx 0.27

---

## 파일 구조

```
app/
  __init__.py
  main.py                      # FastAPI 앱 + 라우터 등록
  core/
    __init__.py
    config.py                  # 환경변수 설정 (pydantic-settings)
    database.py                # SQLAlchemy async engine + session + Base
    redis_client.py            # Redis 연결 풀
  models/
    __init__.py
    ingredient.py              # IngredientMaster ORM 모델
    inventory.py               # UserInventory ORM 모델
  schemas/
    __init__.py
    common.py                  # ApiResponse[T], ApiErrorResponse
    ingredient.py              # IngredientMasterRead
    inventory.py               # InventoryCreate, InventoryRead, InventoryDashboard
  routers/
    __init__.py
    ingredients.py             # GET /api/v1/ingredients, GET /api/v1/ingredients/{id}
    inventory.py               # POST·GET /api/v1/inventory
  services/
    __init__.py
    bitset_service.py          # Redis BitSet 조작 (set_bit / clear_bit / get_bitset)
    inventory_service.py       # 식재료 등록, 대시보드, 신호등 분류, α-스코어
  dependencies/
    __init__.py
    auth.py                    # get_current_user_id (X-User-ID 헤더, 향후 교체)
tests/
  __init__.py
  conftest.py                  # mock_db / mock_redis / async client fixtures
  test_ingredients.py
  test_inventory.py
  test_bitset_service.py
.env.example
pytest.ini
requirements.txt
```

---

## Task 1: 프로젝트 스켈레톤

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `.env.example`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/core/__init__.py`, `app/models/__init__.py`, `app/schemas/__init__.py`, `app/routers/__init__.py`, `app/services/__init__.py`, `app/dependencies/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: 디렉토리 생성**

```bash
mkdir -p app/core app/models app/schemas app/routers app/services app/dependencies tests
touch app/__init__.py app/core/__init__.py app/models/__init__.py
touch app/schemas/__init__.py app/routers/__init__.py app/services/__init__.py
touch app/dependencies/__init__.py tests/__init__.py
```

- [ ] **Step 2: requirements.txt 작성**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
redis==5.2.0
pydantic-settings==2.6.1
python-dotenv==1.0.1
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
```

- [ ] **Step 3: pytest.ini 작성**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 4: .env.example 작성**

```
# Supabase PostgreSQL 직접 연결 (Supabase 대시보드 → Settings → Database → Connection string)
DATABASE_URL=postgresql+asyncpg://postgres:[password]@db.[project-ref].supabase.co:5432/postgres

# Redis
REDIS_URL=redis://localhost:6379
```

- [ ] **Step 5: app/main.py 작성**

```python
from fastapi import FastAPI
from app.routers import ingredients, inventory

app = FastAPI(title="냉장고 재고 관리 API", version="0.1.0")

app.include_router(ingredients.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

- [ ] **Step 6: 의존성 설치**

```bash
pip install -r requirements.txt
```

Expected: 모든 패키지 설치 완료, 에러 없음

- [ ] **Step 7: 서버 기동 확인**

```bash
uvicorn app.main:app --reload
```

Expected: `http://127.0.0.1:8000/health` → `{"status": "ok"}`

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "feat: initialize FastAPI project skeleton"
```

---

## Task 2: 설정 + DB 연결 + Redis 연결

**Files:**
- Create: `app/core/config.py`
- Create: `app/core/database.py`
- Create: `app/core/redis_client.py`

- [ ] **Step 1: app/core/config.py 작성**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379"

    model_config = {"env_file": ".env"}


settings = Settings()
```

- [ ] **Step 2: app/core/database.py 작성**

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 3: app/core/redis_client.py 작성**

```python
import redis.asyncio as aioredis
from app.core.config import settings

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=False)
    return _redis
```

- [ ] **Step 4: .env 파일 생성 (로컬 전용, git 제외)**

```bash
cp .env.example .env
# .env를 열어 실제 Supabase DATABASE_URL과 REDIS_URL 입력
```

- [ ] **Step 5: 설정 로딩 확인**

```bash
python -c "from app.core.config import settings; print(settings.database_url[:30])"
```

Expected: DATABASE_URL 앞부분 출력, 에러 없음

- [ ] **Step 6: Commit**

```bash
git add app/core/
git commit -m "feat: add config, database, and redis connections"
```

---

## Task 3: 공통 API 응답 스키마

**Files:**
- Create: `app/schemas/common.py`

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_common.py**

```python
from app.schemas.common import ApiResponse, ApiErrorResponse


def test_api_response_success():
    resp = ApiResponse(success=True, data={"key": "value"}, message="ok")
    assert resp.success is True
    assert resp.data == {"key": "value"}


def test_api_response_error():
    resp = ApiErrorResponse(error={"code": "NOT_FOUND", "message": "없음"})
    assert resp.success is False
    assert resp.error.code == "NOT_FOUND"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
pytest tests/test_common.py -v
```

Expected: `ImportError` (모듈 없음)

- [ ] **Step 3: app/schemas/common.py 작성**

```python
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: str = ""


class ErrorDetail(BaseModel):
    code: str
    message: str


class ApiErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_common.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/schemas/common.py tests/test_common.py
git commit -m "feat: add common ApiResponse schema"
```

---

## Task 4: IngredientMaster 모델 + 스키마

**Files:**
- Create: `app/models/ingredient.py`
- Create: `app/schemas/ingredient.py`

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_ingredients.py**

```python
from app.schemas.ingredient import IngredientMasterRead
from decimal import Decimal


def test_ingredient_master_read_schema():
    data = {
        "id": 1,
        "bit_id": 0,
        "name": "양파",
        "category": "채소",
        "default_shelf_days": 30,
        "risk_factor": Decimal("1"),
    }
    obj = IngredientMasterRead.model_validate(data)
    assert obj.name == "양파"
    assert obj.risk_factor == Decimal("1")
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
pytest tests/test_ingredients.py::test_ingredient_master_read_schema -v
```

Expected: `ImportError`

- [ ] **Step 3: app/models/ingredient.py 작성**

```python
from sqlalchemy import Column, BigInteger, Integer, String, Numeric
from app.core.database import Base


class IngredientMaster(Base):
    __tablename__ = "ingredient_master"

    id = Column(BigInteger, primary_key=True)
    bit_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    default_shelf_days = Column(Integer, nullable=False)
    risk_factor = Column(Numeric, nullable=False)
```

- [ ] **Step 4: app/schemas/ingredient.py 작성**

```python
from pydantic import BaseModel
from decimal import Decimal


class IngredientMasterRead(BaseModel):
    id: int
    bit_id: int
    name: str
    category: str
    default_shelf_days: int
    risk_factor: Decimal

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_ingredients.py::test_ingredient_master_read_schema -v
```

Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add app/models/ingredient.py app/schemas/ingredient.py tests/test_ingredients.py
git commit -m "feat: add IngredientMaster model and schema"
```

---

## Task 5: 테스트 인프라 (conftest.py)

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: tests/conftest.py 작성**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from app.main import app
from app.core.database import get_db
from app.core.redis_client import get_redis


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
async def client(mock_db, mock_redis):
    async def override_get_db():
        yield mock_db

    async def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
```

- [ ] **Step 2: health check 테스트로 conftest 동작 확인**

`tests/test_ingredients.py` 맨 위에 추가:

```python
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

- [ ] **Step 3: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_ingredients.py::test_health -v
```

Expected: 1 passed

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_ingredients.py
git commit -m "test: add conftest with mock fixtures and health check"
```

---

## Task 6: Ingredients 라우터 (GET /api/v1/ingredients)

**Files:**
- Create: `app/routers/ingredients.py`
- Modify: `tests/test_ingredients.py`

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_ingredients.py 에 추가**

```python
from unittest.mock import MagicMock, AsyncMock
from decimal import Decimal


def _make_ingredient(name="양파", category="채소", bit_id=0):
    ing = MagicMock()
    ing.id = 1
    ing.bit_id = bit_id
    ing.name = name
    ing.category = category
    ing.default_shelf_days = 30
    ing.risk_factor = Decimal("1")
    return ing


async def test_get_ingredients_list(client, mock_db):
    ing = _make_ingredient()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [ing]
    mock_db.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/v1/ingredients")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "양파"


async def test_get_ingredient_by_id(client, mock_db):
    ing = _make_ingredient()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = ing
    mock_db.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/v1/ingredients/1")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == 1


async def test_get_ingredient_not_found(client, mock_db):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/v1/ingredients/999")
    assert resp.status_code == 404
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
pytest tests/test_ingredients.py -v -k "not test_ingredient_master_read_schema and not test_health"
```

Expected: 3 failed (라우터 없음)

- [ ] **Step 3: app/routers/ingredients.py 작성**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.core.database import get_db
from app.models.ingredient import IngredientMaster
from app.schemas.ingredient import IngredientMasterRead
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("", response_model=ApiResponse[List[IngredientMasterRead]])
async def list_ingredients(
    q: Optional[str] = Query(None, description="식재료명 검색"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(IngredientMaster)
    if q:
        stmt = stmt.where(IngredientMaster.name.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(IngredientMaster.category == category)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return ApiResponse(success=True, data=items)


@router.get("/{ingredient_id}", response_model=ApiResponse[IngredientMasterRead])
async def get_ingredient(ingredient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IngredientMaster).where(IngredientMaster.id == ingredient_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return ApiResponse(success=True, data=item)
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_ingredients.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/routers/ingredients.py tests/test_ingredients.py
git commit -m "feat: add GET /api/v1/ingredients endpoints"
```

---

## Task 7: user_inventory 테이블 SQL 마이그레이션

**Files:**
- Create: `docs/migrations/001_create_user_inventory.sql`

> Supabase 대시보드 → SQL Editor에서 직접 실행할 SQL이다.

- [ ] **Step 1: SQL 파일 작성 — docs/migrations/001_create_user_inventory.sql**

```sql
-- user_inventory: 사용자별 보유 식재료 인스턴스 (FIFO 차감 단위)
CREATE TABLE IF NOT EXISTS user_inventory (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    ingredient_master_id BIGINT NOT NULL REFERENCES ingredient_master(id),
    quantity    NUMERIC NOT NULL DEFAULT 1,
    unit        VARCHAR(50),
    expire_date DATE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_inventory_user_id
    ON user_inventory(user_id);

CREATE INDEX IF NOT EXISTS idx_user_inventory_expire_date
    ON user_inventory(user_id, expire_date ASC);
```

- [ ] **Step 2: Supabase SQL Editor에서 실행**

Supabase 대시보드 → SQL Editor → 위 SQL 붙여넣기 → Run

Expected: `Success. No rows returned`

- [ ] **Step 3: 테이블 생성 확인**

Supabase 대시보드 → Table Editor → `user_inventory` 테이블 확인

- [ ] **Step 4: Commit**

```bash
mkdir -p docs/migrations
git add docs/migrations/001_create_user_inventory.sql
git commit -m "chore: add user_inventory migration SQL"
```

---

## Task 8: UserInventory 모델 + 재고 스키마

**Files:**
- Create: `app/models/inventory.py`
- Create: `app/schemas/inventory.py`

- [ ] **Step 1: app/models/inventory.py 작성**

```python
from sqlalchemy import Column, BigInteger, String, Numeric, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserInventory(Base):
    __tablename__ = "user_inventory"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(String, nullable=False)
    ingredient_master_id = Column(BigInteger, ForeignKey("ingredient_master.id"), nullable=False)
    quantity = Column(Numeric, nullable=False)
    unit = Column(String(50))
    expire_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ingredient = relationship("IngredientMaster", lazy="raise")
```

- [ ] **Step 2: app/schemas/inventory.py 작성**

```python
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Literal
from app.schemas.ingredient import IngredientMasterRead


class InventoryCreate(BaseModel):
    ingredient_master_id: int
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit: Optional[str] = None
    expire_date: Optional[date] = None  # None이면 default_shelf_days로 자동 계산


class InventoryRead(BaseModel):
    id: int
    user_id: str
    ingredient_master_id: int
    quantity: Decimal
    unit: Optional[str]
    expire_date: date
    created_at: datetime
    ingredient: IngredientMasterRead
    traffic_light: Literal["red", "yellow", "green"] = "green"
    score: float = 0.0

    model_config = {"from_attributes": True}


class InventoryDashboard(BaseModel):
    items: list[InventoryRead]
    total: int
```

- [ ] **Step 3: 스키마 임포트 확인**

```bash
python -c "from app.schemas.inventory import InventoryCreate, InventoryRead, InventoryDashboard; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/models/inventory.py app/schemas/inventory.py
git commit -m "feat: add UserInventory model and inventory schemas"
```

---

## Task 9: BitSet 서비스

**Files:**
- Create: `app/services/bitset_service.py`
- Create: `tests/test_bitset_service.py`

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_bitset_service.py**

```python
import pytest
from unittest.mock import AsyncMock
from app.services.bitset_service import set_bit, clear_bit, get_user_bitset, has_bit

BYTE_LEN = (427 + 7) // 8  # 54 bytes


@pytest.fixture
def redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock()
    return r


async def test_set_bit_on_empty(redis):
    await set_bit(redis, "user1", 0)
    redis.set.assert_called_once()
    args = redis.set.call_args[0]
    stored = int.from_bytes(args[1], "big")
    assert stored & (1 << 0)


async def test_clear_bit(redis):
    # bit 5가 켜진 상태로 시작
    initial = (1 << 5).to_bytes(BYTE_LEN, "big")
    redis.get = AsyncMock(return_value=initial)

    await clear_bit(redis, "user1", 5)
    args = redis.set.call_args[0]
    stored = int.from_bytes(args[1], "big")
    assert not (stored & (1 << 5))


async def test_has_bit_true(redis):
    initial = (1 << 3).to_bytes(BYTE_LEN, "big")
    redis.get = AsyncMock(return_value=initial)
    assert await has_bit(redis, "user1", 3) is True


async def test_has_bit_false(redis):
    assert await has_bit(redis, "user1", 3) is False


async def test_get_user_bitset_empty(redis):
    assert await get_user_bitset(redis, "user1") == 0
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
pytest tests/test_bitset_service.py -v
```

Expected: 5 failed (모듈 없음)

- [ ] **Step 3: app/services/bitset_service.py 작성**

```python
import redis.asyncio as aioredis

_TOTAL = 427
_BYTE_LEN = (_TOTAL + 7) // 8  # 54 bytes


def _key(user_id: str) -> str:
    return f"user:{user_id}:bitset"


async def get_user_bitset(redis: aioredis.Redis, user_id: str) -> int:
    val = await redis.get(_key(user_id))
    return int.from_bytes(val, "big") if val else 0


async def set_bit(redis: aioredis.Redis, user_id: str, bit_id: int) -> None:
    current = await get_user_bitset(redis, user_id)
    updated = current | (1 << bit_id)
    await redis.set(_key(user_id), updated.to_bytes(_BYTE_LEN, "big"))


async def clear_bit(redis: aioredis.Redis, user_id: str, bit_id: int) -> None:
    current = await get_user_bitset(redis, user_id)
    updated = current & ~(1 << bit_id)
    await redis.set(_key(user_id), updated.to_bytes(_BYTE_LEN, "big"))


async def has_bit(redis: aioredis.Redis, user_id: str, bit_id: int) -> bool:
    current = await get_user_bitset(redis, user_id)
    return bool(current & (1 << bit_id))
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_bitset_service.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/bitset_service.py tests/test_bitset_service.py
git commit -m "feat: add Redis BitSet service"
```

---

## Task 10: 임시 인증 의존성 + Inventory 라우터 뼈대

**Files:**
- Create: `app/dependencies/auth.py`
- Create: `app/routers/inventory.py` (뼈대)

- [ ] **Step 1: app/dependencies/auth.py 작성**

```python
from fastapi import Header, HTTPException


async def get_current_user_id(x_user_id: str = Header(..., alias="X-User-ID")) -> str:
    """임시 인증: X-User-ID 헤더에서 user_id 추출. 실제 인증 구현 시 이 함수만 교체."""
    if not x_user_id.strip():
        raise HTTPException(status_code=401, detail="X-User-ID header is required")
    return x_user_id.strip()
```

- [ ] **Step 2: app/routers/inventory.py 뼈대 작성**

```python
from fastapi import APIRouter

router = APIRouter(prefix="/inventory", tags=["inventory"])
```

- [ ] **Step 3: 서버 재기동 후 /docs 확인**

```bash
uvicorn app.main:app --reload
```

Expected: `http://127.0.0.1:8000/docs` 에서 ingredients, inventory 태그 확인

- [ ] **Step 4: Commit**

```bash
git add app/dependencies/auth.py app/routers/inventory.py
git commit -m "feat: add temporary auth dependency and inventory router scaffold"
```

---

## Task 11: F-01 — 식재료 등록 (POST /api/v1/inventory)

**Files:**
- Create: `app/services/inventory_service.py`
- Modify: `app/routers/inventory.py`
- Create: `tests/test_inventory.py`

- [ ] **Step 1: 실패하는 테스트 작성 — tests/test_inventory.py**

```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from decimal import Decimal
from datetime import date, timedelta, datetime


def _make_ingredient(bit_id=5, default_shelf_days=7):
    ing = MagicMock()
    ing.id = 1
    ing.bit_id = bit_id
    ing.name = "양파"
    ing.category = "채소"
    ing.default_shelf_days = default_shelf_days
    ing.risk_factor = Decimal("1")
    return ing


def _make_inventory_item(ingredient):
    item = MagicMock()
    item.id = 10
    item.user_id = "user1"
    item.ingredient_master_id = ingredient.id
    item.quantity = Decimal("2")
    item.unit = "개"
    item.expire_date = date.today() + timedelta(days=7)
    item.created_at = datetime.now()
    item.ingredient = ingredient
    return item


async def test_post_inventory_registers_ingredient(client, mock_db, mock_redis):
    ing = _make_ingredient()
    item = _make_inventory_item(ing)

    # db.execute: ingredient 조회
    find_result = MagicMock()
    find_result.scalar_one_or_none.return_value = ing
    mock_db.execute = AsyncMock(return_value=find_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "ingredient", ing))

    # redis: 기존 bitset 없음
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    resp = await client.post(
        "/api/v1/inventory",
        json={"ingredient_master_id": 1, "quantity": "2", "unit": "개"},
        headers={"X-User-ID": "user1"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    mock_redis.set.assert_called_once()  # BitSet 갱신됨


async def test_post_inventory_ingredient_not_found(client, mock_db, mock_redis):
    find_result = MagicMock()
    find_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=find_result)

    resp = await client.post(
        "/api/v1/inventory",
        json={"ingredient_master_id": 9999, "quantity": "1"},
        headers={"X-User-ID": "user1"},
    )
    assert resp.status_code == 404


async def test_post_inventory_requires_user_id(client):
    resp = await client.post(
        "/api/v1/inventory",
        json={"ingredient_master_id": 1, "quantity": "1"},
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
pytest tests/test_inventory.py -v
```

Expected: 3 failed

- [ ] **Step 3: app/services/inventory_service.py 작성 (register_ingredient)**

```python
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis
from fastapi import HTTPException
from app.models.ingredient import IngredientMaster
from app.models.inventory import UserInventory
from app.schemas.inventory import InventoryCreate
from app.services.bitset_service import set_bit


async def register_ingredient(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    data: InventoryCreate,
) -> UserInventory:
    result = await db.execute(
        select(IngredientMaster).where(IngredientMaster.id == data.ingredient_master_id)
    )
    ingredient = result.scalar_one_or_none()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    expire_date = data.expire_date or (date.today() + timedelta(days=ingredient.default_shelf_days))
    unit = data.unit or "개"

    item = UserInventory(
        user_id=user_id,
        ingredient_master_id=data.ingredient_master_id,
        quantity=data.quantity,
        unit=unit,
        expire_date=expire_date,
    )
    item.ingredient = ingredient  # relationship 미리 세팅
    db.add(item)
    await db.commit()
    await db.refresh(item)

    await set_bit(redis, user_id, ingredient.bit_id)
    return item
```

- [ ] **Step 4: app/routers/inventory.py 에 POST 엔드포인트 추가**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.dependencies.auth import get_current_user_id
from app.schemas.inventory import InventoryCreate, InventoryRead
from app.schemas.common import ApiResponse
from app.services.inventory_service import register_ingredient

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("", response_model=ApiResponse[InventoryRead], status_code=201)
async def add_inventory(
    data: InventoryCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    item = await register_ingredient(db, redis, user_id, data)
    return ApiResponse(success=True, data=item, message="재료가 등록되었습니다.")
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_inventory.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add app/services/inventory_service.py app/routers/inventory.py tests/test_inventory.py
git commit -m "feat: implement F-01 ingredient registration (POST /api/v1/inventory)"
```

---

## Task 12: F-02 — 재고 대시보드 (GET /api/v1/inventory)

**Files:**
- Modify: `app/services/inventory_service.py` (get_dashboard, 신호등, α-스코어 추가)
- Modify: `app/routers/inventory.py` (GET 엔드포인트 추가)
- Modify: `tests/test_inventory.py` (F-02 테스트 추가)

- [ ] **Step 1: 실패하는 테스트 — tests/test_inventory.py 에 추가**

```python
async def test_get_inventory_dashboard(client, mock_db, mock_redis):
    ing = _make_ingredient(bit_id=5, default_shelf_days=7)
    item = _make_inventory_item(ing)

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [item]
    mock_db.execute = AsyncMock(return_value=list_result)

    resp = await client.get("/api/v1/inventory", headers={"X-User-ID": "user1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total"] == 1
    first = body["data"]["items"][0]
    assert "traffic_light" in first
    assert first["traffic_light"] in ("red", "yellow", "green")
    assert "score" in first


async def test_get_inventory_sorted_by_expire_date(client, mock_db, mock_redis):
    ing = _make_ingredient()
    item = _make_inventory_item(ing)

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [item]
    mock_db.execute = AsyncMock(return_value=list_result)

    resp = await client.get(
        "/api/v1/inventory?sort=expire_date", headers={"X-User-ID": "user1"}
    )
    assert resp.status_code == 200


async def test_get_inventory_requires_user_id(client):
    resp = await client.get("/api/v1/inventory")
    assert resp.status_code == 422
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
pytest tests/test_inventory.py -v -k "dashboard or expire_date or requires_user"
```

Expected: 3 failed

- [ ] **Step 3: app/services/inventory_service.py 에 대시보드 로직 추가**

기존 import 아래에 추가 (`date`, `select`, `AsyncSession`은 Task 11에서 이미 임포트됨):

```python
from typing import Literal
from app.schemas.inventory import InventoryCreate, InventoryRead, InventoryDashboard


def _calc_score(risk_factor: float, quantity: float, expire_date: date) -> float:
    days_left = max(1, (expire_date - date.today()).days)
    return risk_factor * quantity / (days_left ** 2 + 1)


def _traffic_light(expire_date: date, risk_factor: float) -> Literal["red", "yellow", "green"]:
    """신호등 분류. 임계값 미확정 — 팀 내 확정 후 수정 필요."""
    days_left = (expire_date - date.today()).days
    if days_left <= 2 or (days_left <= 5 and risk_factor >= 2):
        return "red"
    if days_left <= 5 or (days_left <= 10 and risk_factor >= 2):
        return "yellow"
    return "green"


async def get_dashboard(
    db: AsyncSession,
    user_id: str,
    sort: str = "recommended",
) -> InventoryDashboard:
    result = await db.execute(
        select(UserInventory).where(UserInventory.user_id == user_id)
    )
    items = result.scalars().all()

    reads: list[InventoryRead] = []
    for item in items:
        rf = float(item.ingredient.risk_factor)
        score = _calc_score(rf, float(item.quantity), item.expire_date)
        tl = _traffic_light(item.expire_date, rf)
        reads.append(
            InventoryRead.model_validate(item).model_copy(
                update={"traffic_light": tl, "score": score}
            )
        )

    if sort == "expire_date":
        reads.sort(key=lambda x: x.expire_date)
    else:
        reads.sort(key=lambda x: x.score, reverse=True)

    return InventoryDashboard(items=reads, total=len(reads))
```

- [ ] **Step 4: app/routers/inventory.py 에 GET 엔드포인트 추가**

기존 import에 추가:
```python
from fastapi import Query
from typing import Literal
from app.schemas.inventory import InventoryDashboard
from app.services.inventory_service import register_ingredient, get_dashboard
```

라우터에 추가:
```python
@router.get("", response_model=ApiResponse[InventoryDashboard])
async def get_inventory(
    sort: Literal["recommended", "expire_date"] = Query(default="recommended"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    dashboard = await get_dashboard(db, user_id, sort)
    return ApiResponse(success=True, data=dashboard)
```

- [ ] **Step 5: 테스트 전체 실행 → 모두 통과 확인**

```bash
pytest -v
```

Expected: 전체 통과 (test_common, test_ingredients, test_bitset_service, test_inventory)

- [ ] **Step 6: Commit**

```bash
git add app/services/inventory_service.py app/routers/inventory.py tests/test_inventory.py
git commit -m "feat: implement F-02 inventory dashboard with traffic light and alpha-score (GET /api/v1/inventory)"
```

---

## 완료 후 실 서버 연결 확인

- [ ] `.env` 파일에 실제 Supabase DATABASE_URL, REDIS_URL 입력 확인
- [ ] Supabase에서 Task 7의 SQL 마이그레이션 실행 확인
- [ ] `uvicorn app.main:app --reload` 기동 후 `/docs` 접속
- [ ] POST `/api/v1/inventory` 에 실 식재료 등록 테스트
- [ ] GET `/api/v1/inventory` 에서 신호등·스코어 포함 응답 확인
