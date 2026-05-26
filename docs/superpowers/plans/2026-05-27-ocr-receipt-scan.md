# OCR 영수증 스캔 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CLOVA OCR API로 영수증 이미지를 스캔하여 식재료를 인식하고, 사용자 확정 후 인벤토리에 일괄 등록하는 2-step 플로우 구현

**Architecture:** `ocr_service.py`가 CLOVA API를 호출하고, `matching_service.py`가 품목명을 `ingredient_master` 테이블과 매칭한다. `ocr.py` 라우터가 `/scan` · `/confirm` 두 엔드포인트를 노출하며, confirm은 기존 `register_ingredient`를 재사용한다.

**Tech Stack:** FastAPI, SQLAlchemy async (asyncpg), httpx 0.27.2 (이미 포함), rapidfuzz, Pydantic v2, pytest-asyncio

---

## 파일 구조

| 파일 | 상태 | 역할 |
|------|------|------|
| `app/schemas/ocr.py` | 신규 | OCR 요청/응답 Pydantic 스키마 |
| `app/services/ocr_service.py` | 신규 | CLOVA API 호출 및 응답 파싱 |
| `app/services/matching_service.py` | 신규 | 품목명 → ingredient_master 매칭 |
| `app/routers/ocr.py` | 신규 | `/ocr/scan`, `/ocr/confirm` 엔드포인트 |
| `app/core/config.py` | 수정 | `clova_ocr_url`, `clova_ocr_secret` 추가 |
| `app/main.py` | 수정 | ocr 라우터 등록 + openapi_tags 추가 |
| `requirements.txt` | 수정 | `rapidfuzz>=3.0.0` 추가 |
| `.env.example` | 수정 | OCR 환경변수 예시 추가 |
| `tests/test_ocr_service.py` | 신규 | ocr_service 단위 테스트 (CLOVA mock) |
| `tests/test_matching_service.py` | 신규 | matching_service 단위 테스트 (DB mock) |
| `tests/test_ocr_router.py` | 신규 | HTTP 통합 테스트 (service mock) |

---

## Task 1: Worktree 생성 및 의존성·설정 추가

**Files:**
- Modify: `requirements.txt`
- Modify: `app/core/config.py`
- Modify: `.env.example` (없으면 생성)

- [ ] **Step 1: Worktree 생성**

메인 레포 루트(`C:\Dev\Capstone_BE_A2`)에서 실행:

```powershell
git worktree add .worktrees/feature-ocr-scan -b feature/ocr-scan
```

이후 모든 작업은 `.worktrees/feature-ocr-scan` 디렉토리에서 수행.

- [ ] **Step 2: rapidfuzz를 requirements.txt에 추가**

`requirements.txt` 끝에 한 줄 추가:

```
rapidfuzz>=3.0.0
```

- [ ] **Step 3: config.py에 CLOVA 설정 추가**

`app/core/config.py`의 `Settings` 클래스에 두 필드 추가:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379"
    supabase_url: str
    supabase_anon_key: str
    docs_username: str = "admin"
    docs_password: str = "changeme"
    cors_origins: list[str] = ["http://localhost:3000"]
    clova_ocr_url: str = ""
    clova_ocr_secret: str = ""

    model_config = {"env_file": (".env", ".env.local"), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
```

- [ ] **Step 4: .env.example 생성/수정**

`.env.example` 파일 끝에 추가 (파일이 없으면 생성):

```
# CLOVA OCR
CLOVA_OCR_URL=https://your-ocr-invoke-url.apigw.ntruss.com/custom/v1/...
CLOVA_OCR_SECRET=your-x-ocr-secret-here
```

- [ ] **Step 5: 커밋**

```bash
git add requirements.txt app/core/config.py .env.example
git commit -m "chore: add rapidfuzz dependency and CLOVA OCR config settings"
```

---

## Task 2: OCR 스키마 정의 (`app/schemas/ocr.py`)

**Files:**
- Create: `app/schemas/ocr.py`
- Create: `tests/test_ocr_schemas.py`

- [ ] **Step 1: 실패하는 스키마 테스트 작성**

`tests/test_ocr_schemas.py`:

```python
import pytest
from datetime import date
from decimal import Decimal
from pydantic import ValidationError

from app.schemas.ocr import (
    OcrRawItem,
    OcrCandidate,
    OcrScanCandidate,
    OcrScanResult,
    OcrConfirmItem,
    OcrConfirmRequest,
    OcrConfirmError,
    OcrConfirmResult,
)


def test_ocr_raw_item():
    item = OcrRawItem(text="닭가슴살200g")
    assert item.text == "닭가슴살200g"


def test_ocr_candidate():
    c = OcrCandidate(ingredient_master_id=5, ingredient_name="닭가슴살", confidence=95.2)
    assert c.confidence == 95.2


def test_ocr_scan_candidate_register():
    c = OcrScanCandidate(
        raw_text="닭가슴살200g",
        recommended_action="register",
        candidates=[OcrCandidate(ingredient_master_id=5, ingredient_name="닭가슴살", confidence=95.2)],
    )
    assert c.recommended_action == "register"
    assert len(c.candidates) == 1


def test_ocr_scan_candidate_skip():
    c = OcrScanCandidate(raw_text="비닐봉투", recommended_action="skip", candidates=[])
    assert c.candidates == []


def test_ocr_scan_result():
    r = OcrScanResult(items=[])
    assert r.items == []


def test_ocr_confirm_item_with_expire():
    item = OcrConfirmItem(
        ingredient_master_id=5,
        quantity=Decimal("200.0"),
        expire_date=date(2026, 6, 10),
    )
    assert item.expire_date == date(2026, 6, 10)


def test_ocr_confirm_item_without_expire():
    item = OcrConfirmItem(ingredient_master_id=5, quantity=Decimal("1.0"))
    assert item.expire_date is None


def test_ocr_confirm_item_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        OcrConfirmItem(ingredient_master_id=5, quantity=Decimal("0"))


def test_ocr_confirm_request():
    req = OcrConfirmRequest(items=[
        OcrConfirmItem(ingredient_master_id=5, quantity=Decimal("200.0")),
    ])
    assert len(req.items) == 1


def test_ocr_confirm_result_defaults():
    r = OcrConfirmResult(registered=[], errors=[])
    assert r.registered == []
    assert r.errors == []


def test_ocr_confirm_error():
    e = OcrConfirmError(ingredient_master_id=999, reason="Ingredient not found")
    assert e.ingredient_master_id == 999
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
cd .worktrees/feature-ocr-scan
pytest tests/test_ocr_schemas.py -v
```

기대 결과: `ImportError` 또는 `ModuleNotFoundError` (스키마 파일 없음)

- [ ] **Step 3: 스키마 구현**

`app/schemas/ocr.py`:

```python
from decimal import Decimal
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.inventory import InventoryRead


class OcrRawItem(BaseModel):
    text: str


class OcrCandidate(BaseModel):
    ingredient_master_id: int
    ingredient_name: str
    confidence: float


class OcrScanCandidate(BaseModel):
    raw_text: str
    recommended_action: Literal["register", "skip"]
    candidates: list[OcrCandidate]


class OcrScanResult(BaseModel):
    items: list[OcrScanCandidate]


class OcrConfirmItem(BaseModel):
    ingredient_master_id: int
    quantity: Decimal = Field(gt=0)
    expire_date: date | None = None


class OcrConfirmRequest(BaseModel):
    items: list[OcrConfirmItem]


class OcrConfirmError(BaseModel):
    ingredient_master_id: int
    reason: str


class OcrConfirmResult(BaseModel):
    registered: list[InventoryRead] = []
    errors: list[OcrConfirmError] = []
```

- [ ] **Step 4: 테스트 실행 → PASS 확인**

```bash
pytest tests/test_ocr_schemas.py -v
```

기대 결과: 모든 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/schemas/ocr.py tests/test_ocr_schemas.py
git commit -m "feat: add OCR Pydantic schemas"
```

---

## Task 3: OCR 서비스 (`app/services/ocr_service.py`)

**Files:**
- Create: `app/services/ocr_service.py`
- Create: `tests/test_ocr_service.py`

- [ ] **Step 1: 실패하는 서비스 테스트 작성**

`tests/test_ocr_service.py`:

```python
import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.ocr_service import scan_receipt
from app.schemas.ocr import OcrRawItem


def _make_clova_response(items: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "images": [{
            "receipt": {
                "result": {
                    "subResults": [{"items": items}]
                }
            }
        }]
    }
    return resp


def _patch_client(mock_response: MagicMock):
    """httpx.AsyncClient context manager 패치 헬퍼."""
    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(return_value=mock_response)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_instance)
    cm.__aexit__ = AsyncMock(return_value=None)
    return patch("app.services.ocr_service.httpx.AsyncClient", return_value=cm)


@pytest.mark.asyncio
async def test_scan_receipt_parses_items():
    mock_resp = _make_clova_response([
        {"name": {"text": "닭가슴살200g"}},
        {"name": {"text": "달걀 10구"}},
    ])
    with _patch_client(mock_resp):
        result = await scan_receipt(b"fake_image", "receipt.jpg")

    assert len(result) == 2
    assert result[0].text == "닭가슴살200g"
    assert result[1].text == "달걀 10구"


@pytest.mark.asyncio
async def test_scan_receipt_skips_empty_text():
    mock_resp = _make_clova_response([
        {"name": {"text": "닭가슴살"}},
        {"name": {"text": "   "}},   # 공백만 있는 텍스트 → 제외
    ])
    with _patch_client(mock_resp):
        result = await scan_receipt(b"fake_image", "receipt.jpg")

    assert len(result) == 1
    assert result[0].text == "닭가슴살"


@pytest.mark.asyncio
async def test_scan_receipt_empty_subresults():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "images": [{"receipt": {"result": {"subResults": []}}}]
    }
    with _patch_client(mock_resp):
        result = await scan_receipt(b"fake_image", "receipt.jpg")

    assert result == []


@pytest.mark.asyncio
async def test_scan_receipt_timeout_propagates():
    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_instance)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.ocr_service.httpx.AsyncClient", return_value=cm):
        with pytest.raises(httpx.TimeoutException):
            await scan_receipt(b"fake_image", "receipt.jpg")
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
pytest tests/test_ocr_service.py -v
```

기대 결과: `ImportError` (서비스 파일 없음)

- [ ] **Step 3: OCR 서비스 구현**

`app/services/ocr_service.py`:

```python
import json
import httpx
from time import time
from uuid import uuid4
from app.core.config import settings
from app.schemas.ocr import OcrRawItem


async def scan_receipt(image_bytes: bytes, filename: str) -> list[OcrRawItem]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    message = {
        "images": [{"format": ext, "name": filename}],
        "requestId": str(uuid4()),
        "version": "V2",
        "timestamp": int(time() * 1000),
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            settings.clova_ocr_url,
            headers={"X-OCR-SECRET": settings.clova_ocr_secret},
            files={
                "message": (None, json.dumps(message), "application/json"),
                "file": (filename, image_bytes),
            },
        )
    resp.raise_for_status()
    data = resp.json()

    items: list[OcrRawItem] = []
    for image in data.get("images", []):
        sub_results = (image.get("receipt") or {}).get("result", {}).get("subResults", [])
        for sub in sub_results:
            for item in sub.get("items", []):
                text = (item.get("name") or {}).get("text", "").strip()
                if text:
                    items.append(OcrRawItem(text=text))
    return items
```

- [ ] **Step 4: 테스트 실행 → PASS 확인**

```bash
pytest tests/test_ocr_service.py -v
```

기대 결과: 4개 테스트 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/services/ocr_service.py tests/test_ocr_service.py
git commit -m "feat: add CLOVA OCR service for receipt scanning"
```

---

## Task 4: 매칭 서비스 (`app/services/matching_service.py`)

**Files:**
- Create: `app/services/matching_service.py`
- Create: `tests/test_matching_service.py`

- [ ] **Step 1: 실패하는 매칭 테스트 작성**

`tests/test_matching_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

from app.services.matching_service import match_items
from app.schemas.ocr import OcrRawItem


def _make_db_mock(names: list[tuple[int, str]]) -> AsyncMock:
    """(id, name) 리스트로 ingredient_master DB mock 생성."""
    masters = [SimpleNamespace(id=id_, name=name) for id_, name in names]
    db = AsyncMock()
    db.execute.return_value.scalars.return_value.all.return_value = masters
    return db


@pytest.mark.asyncio
async def test_match_exact():
    db = _make_db_mock([(5, "닭가슴살"), (2, "달걀")])
    result = await match_items(db, [OcrRawItem(text="닭가슴살")])

    assert len(result) == 1
    assert result[0].raw_text == "닭가슴살"
    assert result[0].recommended_action == "register"
    assert result[0].candidates[0].ingredient_master_id == 5
    assert result[0].candidates[0].confidence == 100.0


@pytest.mark.asyncio
async def test_match_override_egg():
    db = _make_db_mock([(2, "달걀"), (5, "닭가슴살")])
    result = await match_items(db, [OcrRawItem(text="계란")])

    assert result[0].recommended_action == "register"
    assert result[0].candidates[0].ingredient_master_id == 2  # "달걀"로 매핑됨


@pytest.mark.asyncio
async def test_match_exclude_keyword():
    db = _make_db_mock([(1, "닭가슴살")])
    result = await match_items(db, [OcrRawItem(text="비닐봉투")])

    assert result[0].recommended_action == "skip"
    assert result[0].candidates == []


@pytest.mark.asyncio
async def test_match_fuzzy_high_confidence():
    db = _make_db_mock([(5, "닭가슴살"), (2, "달걀"), (10, "돼지고기")])
    result = await match_items(db, [OcrRawItem(text="닭가슴살200g")])

    assert result[0].recommended_action == "register"
    assert len(result[0].candidates) <= 3
    # 첫 번째 후보가 "닭가슴살"이어야 함
    assert result[0].candidates[0].ingredient_master_id == 5


@pytest.mark.asyncio
async def test_match_low_confidence_skip():
    db = _make_db_mock([(1, "사과"), (2, "배")])
    result = await match_items(db, [OcrRawItem(text="xyzabc_완전다름!!")])

    assert result[0].recommended_action == "skip"


@pytest.mark.asyncio
async def test_match_empty_items():
    db = _make_db_mock([(5, "닭가슴살")])
    result = await match_items(db, [])

    assert result == []


@pytest.mark.asyncio
async def test_match_multiple_items():
    db = _make_db_mock([(5, "닭가슴살"), (2, "달걀")])
    result = await match_items(db, [
        OcrRawItem(text="닭가슴살"),
        OcrRawItem(text="비닐봉투"),
        OcrRawItem(text="계란"),
    ])

    assert len(result) == 3
    assert result[0].recommended_action == "register"
    assert result[1].recommended_action == "skip"
    assert result[2].recommended_action == "register"
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
pytest tests/test_matching_service.py -v
```

기대 결과: `ImportError` (서비스 파일 없음)

- [ ] **Step 3: 매칭 서비스 구현**

`app/services/matching_service.py`:

```python
from rapidfuzz import process, fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ingredient import IngredientMaster
from app.schemas.ocr import OcrRawItem, OcrScanCandidate, OcrCandidate

_EXCLUDE_KEYWORDS = frozenset([
    "비닐봉투", "봉투", "쿠폰", "적립금", "할인", "부가세", "합계",
    "영수증", "카드", "현금", "거스름돈", "포인트", "영수", "합산",
])

_OVERRIDE: dict[str, str] = {
    "계란": "달걀",
    "란": "달걀",
}

_FUZZY_THRESHOLD = 70


async def match_items(db: AsyncSession, raw_items: list[OcrRawItem]) -> list[OcrScanCandidate]:
    if not raw_items:
        return []

    result = await db.execute(select(IngredientMaster))
    masters = result.scalars().all()
    name_to_id: dict[str, int] = {m.name: m.id for m in masters}
    names = list(name_to_id.keys())

    candidates: list[OcrScanCandidate] = []
    for item in raw_items:
        text = item.text

        if any(kw in text for kw in _EXCLUDE_KEYWORDS):
            candidates.append(OcrScanCandidate(
                raw_text=text, recommended_action="skip", candidates=[],
            ))
            continue

        normalized = _OVERRIDE.get(text, text)

        if normalized in name_to_id:
            candidates.append(OcrScanCandidate(
                raw_text=text,
                recommended_action="register",
                candidates=[OcrCandidate(
                    ingredient_master_id=name_to_id[normalized],
                    ingredient_name=normalized,
                    confidence=100.0,
                )],
            ))
            continue

        fuzzy_matches = process.extract(
            normalized, names, scorer=fuzz.partial_ratio, limit=3,
        )
        match_candidates = [
            OcrCandidate(
                ingredient_master_id=name_to_id[name],
                ingredient_name=name,
                confidence=float(score),
            )
            for name, score, _ in fuzzy_matches
        ]
        best = fuzzy_matches[0][1] if fuzzy_matches else 0
        candidates.append(OcrScanCandidate(
            raw_text=text,
            recommended_action="register" if best >= _FUZZY_THRESHOLD else "skip",
            candidates=match_candidates,
        ))

    return candidates
```

- [ ] **Step 4: 테스트 실행 → PASS 확인**

```bash
pytest tests/test_matching_service.py -v
```

기대 결과: 7개 테스트 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/services/matching_service.py tests/test_matching_service.py
git commit -m "feat: add ingredient matching service with exact and fuzzy matching"
```

---

## Task 5: OCR 라우터 + main.py 등록

**Files:**
- Create: `app/routers/ocr.py`
- Modify: `app/main.py`
- Create: `tests/test_ocr_router.py`

- [ ] **Step 1: 실패하는 라우터 테스트 작성**

`tests/test_ocr_router.py`:

```python
import pytest
from decimal import Decimal
from datetime import date
from types import SimpleNamespace
from io import BytesIO
from unittest.mock import patch, AsyncMock

import httpx
from fastapi import HTTPException

from app.schemas.ocr import OcrScanCandidate, OcrCandidate, OcrScanResult


def _make_scan_candidates() -> list[OcrScanCandidate]:
    return [
        OcrScanCandidate(
            raw_text="닭가슴살200g",
            recommended_action="register",
            candidates=[OcrCandidate(ingredient_master_id=5, ingredient_name="닭가슴살", confidence=95.0)],
        ),
        OcrScanCandidate(raw_text="비닐봉투", recommended_action="skip", candidates=[]),
    ]


def _make_mock_userinventory(ingredient_master_id: int = 5) -> SimpleNamespace:
    """InventoryRead.model_validate(obj) 호환 SimpleNamespace."""
    return SimpleNamespace(
        id=1,
        user_id="user1",
        ingredient_master_id=ingredient_master_id,
        quantity=Decimal("200.0"),
        unit="g",
        expire_date=date(2026, 6, 10),
        created_at=date(2026, 5, 27),
        ingredient=SimpleNamespace(
            id=ingredient_master_id, bit_id=4, name="닭가슴살",
            category="육류", default_shelf_days=5, risk_factor=Decimal("3.0"),
        ),
    )


@pytest.mark.asyncio
async def test_scan_success(client):
    mock_raw = [type("R", (), {"text": "닭가슴살200g"})()]
    mock_candidates = _make_scan_candidates()

    with patch("app.routers.ocr.scan_receipt", AsyncMock(return_value=mock_raw)), \
         patch("app.routers.ocr.match_items", AsyncMock(return_value=mock_candidates)):
        resp = await client.post(
            "/api/v1/ocr/scan",
            files={"image": ("receipt.jpg", BytesIO(b"fake"), "image/jpeg")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    items = body["data"]["items"]
    assert len(items) == 2
    assert items[0]["recommended_action"] == "register"
    assert items[1]["recommended_action"] == "skip"


@pytest.mark.asyncio
async def test_scan_timeout_returns_504(client):
    with patch("app.routers.ocr.scan_receipt",
               AsyncMock(side_effect=httpx.TimeoutException("timeout"))):
        resp = await client.post(
            "/api/v1/ocr/scan",
            files={"image": ("receipt.jpg", BytesIO(b"fake"), "image/jpeg")},
        )

    assert resp.status_code == 504
    assert "timeout" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_confirm_all_success(client):
    mock_inv = _make_mock_userinventory()

    with patch("app.routers.ocr.register_ingredient", AsyncMock(return_value=mock_inv)):
        resp = await client.post(
            "/api/v1/ocr/confirm",
            json={"items": [{"ingredient_master_id": 5, "quantity": "200.0"}]},
        )

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert len(data["registered"]) == 1
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_confirm_partial_failure(client):
    async def side_effect(db, redis, user_id, inv_create):
        if inv_create.ingredient_master_id == 999:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        return _make_mock_userinventory(inv_create.ingredient_master_id)

    with patch("app.routers.ocr.register_ingredient", AsyncMock(side_effect=side_effect)):
        resp = await client.post(
            "/api/v1/ocr/confirm",
            json={"items": [
                {"ingredient_master_id": 5, "quantity": "1.0"},
                {"ingredient_master_id": 999, "quantity": "1.0"},
            ]},
        )

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert len(data["registered"]) == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["ingredient_master_id"] == 999
    assert data["errors"][0]["reason"] == "Ingredient not found"


@pytest.mark.asyncio
async def test_confirm_rejects_zero_quantity(client):
    with patch("app.routers.ocr.register_ingredient", AsyncMock()) as mock_reg:
        resp = await client.post(
            "/api/v1/ocr/confirm",
            json={"items": [{"ingredient_master_id": 5, "quantity": "0"}]},
        )

    assert resp.status_code == 422
    mock_reg.assert_not_called()
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
pytest tests/test_ocr_router.py -v
```

기대 결과: `ImportError` 또는 404 (라우터 미등록)

- [ ] **Step 3: OCR 라우터 구현**

`app/routers/ocr.py`:

```python
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
import httpx

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.dependencies.auth import get_current_user_id
from app.schemas.ocr import OcrScanResult, OcrConfirmRequest, OcrConfirmResult, OcrConfirmError
from app.schemas.inventory import InventoryCreate
from app.schemas.common import ApiResponse
from app.services.ocr_service import scan_receipt
from app.services.matching_service import match_items
from app.services.inventory_service import register_ingredient

router = APIRouter(prefix="/ocr", tags=["ocr"])
_BEARER = {"security": [{"bearerAuth": []}]}
_AUTH_401 = {401: {"description": "Authorization 헤더 없음 또는 토큰 만료·무효"}}


@router.post(
    "/scan",
    response_model=ApiResponse[OcrScanResult],
    summary="영수증 OCR 스캔",
    description=(
        "영수증 이미지를 OCR로 분석하여 식재료 후보 목록을 반환합니다.\n\n"
        "- `recommended_action: register` — 매칭 신뢰도 70% 이상, 등록 권장\n"
        "- `recommended_action: skip` — 매칭 실패 또는 비식재료 품목\n\n"
        "**Bearer 토큰 필수.**"
    ),
    responses={
        **_AUTH_401,
        400: {"description": "지원하지 않는 이미지 포맷"},
        504: {"description": "CLOVA OCR API timeout"},
    },
    openapi_extra=_BEARER,
)
async def scan_receipt_endpoint(
    image: UploadFile = File(..., description="영수증 이미지 (jpeg/png/pdf)"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    image_bytes = await image.read()
    try:
        raw_items = await scan_receipt(image_bytes, image.filename or "receipt.jpg")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="OCR service timeout")
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (400, 415):
            raise HTTPException(status_code=400, detail="지원하지 않는 이미지 형식")
        raise

    candidates = await match_items(db, raw_items)
    return ApiResponse(success=True, data=OcrScanResult(items=candidates))


@router.post(
    "/confirm",
    response_model=ApiResponse[OcrConfirmResult],
    status_code=201,
    summary="OCR 스캔 결과 확정 등록",
    description=(
        "사용자가 확정한 품목을 인벤토리에 일괄 등록합니다.\n\n"
        "- `expire_date` 생략 시 `default_shelf_days` 기준 자동 계산\n"
        "- 일부 항목 실패 시 성공 항목만 등록되고, 실패 항목은 `errors`에 포함됩니다.\n\n"
        "**Bearer 토큰 필수.**"
    ),
    responses={**_AUTH_401},
    openapi_extra=_BEARER,
)
async def confirm_receipt_endpoint(
    data: OcrConfirmRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    registered = []
    errors: list[OcrConfirmError] = []
    for item in data.items:
        try:
            inv_create = InventoryCreate(
                ingredient_master_id=item.ingredient_master_id,
                quantity=item.quantity,
                expire_date=item.expire_date,
            )
            result = await register_ingredient(db, redis, user_id, inv_create)
            registered.append(result)
        except HTTPException as e:
            errors.append(OcrConfirmError(
                ingredient_master_id=item.ingredient_master_id,
                reason=e.detail,
            ))

    return ApiResponse(
        success=True,
        data=OcrConfirmResult(registered=registered, errors=errors),
        message="재고가 등록되었습니다.",
    )
```

- [ ] **Step 4: main.py에 OCR 라우터 등록**

`app/main.py`의 import에 `ocr` 추가:

```python
from app.routers import auth, ingredients, inventory, recipes, ocr
```

`openapi_tags` 리스트에 ocr 태그 추가:

```python
openapi_tags=[
    {"name": "auth", "description": "회원가입, 로그인, 내 정보 조회"},
    {"name": "ingredients", "description": "식재료 마스터 데이터 검색 및 단건 조회"},
    {"name": "inventory", "description": "냉장고 재고 등록·조회·수정·삭제 (인증 필요)"},
    {"name": "recipes", "description": "레시피 추천 조회 및 상세 조회"},
    {"name": "ocr", "description": "영수증 OCR 스캔 및 재고 일괄 등록 (인증 필요)"},
],
```

`app.include_router` 줄들 다음에 ocr 라우터 등록:

```python
app.include_router(auth.router, prefix="/api/v1")
app.include_router(ingredients.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(recipes.router, prefix="/api/v1")
app.include_router(ocr.router, prefix="/api/v1")
```

- [ ] **Step 5: 전체 테스트 실행 → PASS 확인**

```bash
pytest tests/ -v
```

기대 결과: 기존 테스트 포함 전체 PASS. OCR 테스트 5개 모두 PASS.

- [ ] **Step 6: 커밋**

```bash
git add app/routers/ocr.py app/main.py tests/test_ocr_router.py
git commit -m "feat: add OCR router with scan and confirm endpoints"
```
