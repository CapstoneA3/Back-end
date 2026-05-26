# F-04 요리 완료 처리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `POST /recipes/{recipe_id}/cook` 엔드포인트 구현 — 클라이언트가 전달한 재료별 실제 사용량을 α-스코어 내림차순으로 인벤토리에서 차감하고, 재고 완전 소진 시 Redis BitSet 갱신.

**Architecture:** `app/schemas/cooking.py`에 요청/응답 스키마 정의, `app/services/cooking_service.py`에 차감 알고리즘 전담, `app/routers/recipes.py`에 엔드포인트 추가. 라우터는 얇게 유지하고 비즈니스 로직은 서비스 계층에 집중. 워크트리는 `feature/recipe-recommendation`에서 분기하여 레시피 라우터·모델을 상속.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy (asyncpg), Redis (aioredis), Pydantic v2, pytest-asyncio, unittest.mock

---

## 파일 맵

| 파일 | 작업 |
|------|------|
| `.worktrees/feature-cooking-completion/app/schemas/cooking.py` | 신규 — 요청/응답 Pydantic 스키마 |
| `.worktrees/feature-cooking-completion/app/services/cooking_service.py` | 신규 — α-스코어 정렬 + 차감 알고리즘 |
| `.worktrees/feature-cooking-completion/app/routers/recipes.py` | 수정 — `POST /{recipe_id}/cook` 엔드포인트 추가 |
| `.worktrees/feature-cooking-completion/tests/test_cooking_service.py` | 신규 — 스키마 + 서비스 단위 테스트 |
| `.worktrees/feature-cooking-completion/tests/test_cooking_router.py` | 신규 — HTTP 엔드포인트 테스트 |

---

### Task 1: 워크트리 생성 및 기존 테스트 통과 확인

**Files:**
- 변경 없음 (워크트리 생성만)

- [ ] **Step 1: 워크트리 생성**

```bash
# 레포 루트(C:\Dev\Capstone_BE_A2)에서 실행
git worktree add .worktrees/feature-cooking-completion -b feature/cooking-completion feature/recipe-recommendation
```

Expected output: `Preparing worktree (new branch 'feature/cooking-completion')`

- [ ] **Step 2: 기존 테스트 통과 확인**

```bash
cd .worktrees/feature-cooking-completion
python -m pytest tests/ -v --tb=short -q
```

Expected: 모든 기존 테스트 PASS (cooking 관련 파일은 아직 없으므로 ImportError 없음 확인)

---

### Task 2: Pydantic 스키마 (`app/schemas/cooking.py`)

**Files:**
- Create: `app/schemas/cooking.py`
- Test: `tests/test_cooking_service.py`

- [ ] **Step 1: 실패할 스키마 테스트 작성**

`tests/test_cooking_service.py`를 새로 생성:

```python
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError


# ─── Schema tests ──────────────────────────────────────────────────

from app.schemas.cooking import (
    CookRequest,
    CookResult,
    IngredientDeductionResult,
    IngredientUsage,
    InventoryDeduction,
)


def test_cook_request_valid():
    req = CookRequest(ingredients=[
        IngredientUsage(ingredient_master_id=5, quantity=200.0),
    ])
    assert req.ingredients[0].quantity == 200.0
    assert req.ingredients[0].ingredient_master_id == 5


def test_cook_request_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=0.0)])


def test_cook_request_rejects_negative_quantity():
    with pytest.raises(ValidationError):
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=-10.0)])


def test_cook_request_rejects_duplicate_ingredient():
    with pytest.raises(ValidationError):
        CookRequest(ingredients=[
            IngredientUsage(ingredient_master_id=5, quantity=100.0),
            IngredientUsage(ingredient_master_id=5, quantity=50.0),
        ])


def test_cook_request_empty_ingredients_ok():
    req = CookRequest(ingredients=[])
    assert req.ingredients == []


def test_cook_result_schema():
    result = CookResult(recipe_id=7, recipe_name="닭볶음탕", deductions=[])
    assert result.recipe_id == 7
    assert result.deductions == []


def test_inventory_deduction_schema():
    d = InventoryDeduction(inventory_id=10, deducted=150.0, deleted=True)
    assert d.deleted is True


def test_ingredient_deduction_result_schema():
    r = IngredientDeductionResult(
        ingredient_master_id=5,
        ingredient_name="닭가슴살",
        requested=200.0,
        deducted=200.0,
        rows_affected=[InventoryDeduction(inventory_id=10, deducted=150.0, deleted=True)],
    )
    assert r.deducted == 200.0
    assert len(r.rows_affected) == 1
```

- [ ] **Step 2: 실패 확인**

```bash
python -m pytest tests/test_cooking_service.py -v --tb=short -q
```

Expected: `ImportError: cannot import name 'CookRequest' from 'app.schemas.cooking'`

- [ ] **Step 3: 스키마 구현**

`app/schemas/cooking.py` 생성:

```python
from pydantic import BaseModel, Field, model_validator


class IngredientUsage(BaseModel):
    ingredient_master_id: int = Field(description="식재료 마스터 ID")
    quantity: float = Field(gt=0, description="실제 사용량 (0 초과)")


class CookRequest(BaseModel):
    ingredients: list[IngredientUsage] = Field(description="사용한 재료 목록")

    @model_validator(mode="after")
    def no_duplicate_ingredients(self) -> "CookRequest":
        seen: set[int] = set()
        for usage in self.ingredients:
            if usage.ingredient_master_id in seen:
                raise ValueError(
                    f"Duplicate ingredient_master_id: {usage.ingredient_master_id}"
                )
            seen.add(usage.ingredient_master_id)
        return self


class InventoryDeduction(BaseModel):
    inventory_id: int = Field(description="차감된 인벤토리 행 ID")
    deducted: float = Field(description="실제 차감된 수량")
    deleted: bool = Field(description="해당 행 삭제 여부 (수량 완전 소진)")


class IngredientDeductionResult(BaseModel):
    ingredient_master_id: int = Field(description="식재료 마스터 ID")
    ingredient_name: str = Field(description="식재료명")
    requested: float = Field(description="요청한 차감 수량")
    deducted: float = Field(description="실제 차감된 총량 (재고 부족 시 < requested)")
    rows_affected: list[InventoryDeduction] = Field(description="영향받은 인벤토리 행 목록")


class CookResult(BaseModel):
    recipe_id: int = Field(description="요리한 레시피 ID")
    recipe_name: str = Field(description="레시피명")
    deductions: list[IngredientDeductionResult] = Field(description="재료별 차감 결과")
```

- [ ] **Step 4: 통과 확인**

```bash
python -m pytest tests/test_cooking_service.py -v --tb=short -q
```

Expected: 스키마 관련 테스트 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/schemas/cooking.py tests/test_cooking_service.py
git commit -m "feat: F-04 cooking 스키마 및 테스트 추가"
```

---

### Task 3: `_alpha_score` 헬퍼 및 `cooking_service.py` 뼈대

**Files:**
- Create: `app/services/cooking_service.py`
- Test: `tests/test_cooking_service.py` (추가)

- [ ] **Step 1: `_alpha_score` 테스트 추가**

`tests/test_cooking_service.py` 파일 끝에 추가:

```python
# ─── _alpha_score tests ────────────────────────────────────────────

from app.services.cooking_service import _alpha_score


def test_alpha_score_one_day_left():
    exp = date.today() + timedelta(days=1)
    assert _alpha_score(3.0, 200.0, exp) == 3.0 * 200.0 / (1 ** 2 + 1)  # 300.0


def test_alpha_score_clips_expired_to_one():
    exp = date.today() - timedelta(days=5)  # 이미 만료
    assert _alpha_score(1.0, 100.0, exp) == 1.0 * 100.0 / (1 ** 2 + 1)  # 50.0


def test_alpha_score_sooner_expiry_ranks_higher():
    today = date.today()
    urgent = _alpha_score(1.0, 100.0, today + timedelta(days=1))
    safe = _alpha_score(1.0, 100.0, today + timedelta(days=10))
    assert urgent > safe


def test_alpha_score_larger_quantity_ranks_higher_same_expiry():
    today = date.today()
    big = _alpha_score(1.0, 200.0, today + timedelta(days=5))
    small = _alpha_score(1.0, 100.0, today + timedelta(days=5))
    assert big > small
```

- [ ] **Step 2: 실패 확인**

```bash
python -m pytest tests/test_cooking_service.py -v --tb=short -q -k "alpha"
```

Expected: `ImportError: cannot import name '_alpha_score' from 'app.services.cooking_service'`

- [ ] **Step 3: `cooking_service.py` 뼈대 생성 (함수 스텁 포함)**

`app/services/cooking_service.py` 생성:

```python
from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from app.models.recipe import Recipe
from app.models.inventory import UserInventory
from app.models.ingredient import IngredientMaster
from app.schemas.cooking import (
    CookRequest,
    CookResult,
    IngredientDeductionResult,
    InventoryDeduction,
)
from app.services.bitset_service import clear_bit


def _alpha_score(risk_factor: float, quantity: float, expire_date: date) -> float:
    """α-스코어: 높을수록 먼저 차감. D-day² 분모로 임박 재료 우선."""
    days_left = max(1, (expire_date - date.today()).days)
    return risk_factor * quantity / (days_left ** 2 + 1)


async def cook_recipe(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    recipe_id: int,
    data: CookRequest,
) -> CookResult:
    raise NotImplementedError
```

- [ ] **Step 4: `_alpha_score` 테스트 통과 확인**

```bash
python -m pytest tests/test_cooking_service.py -v --tb=short -q -k "alpha"
```

Expected: 4개 모두 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/services/cooking_service.py tests/test_cooking_service.py
git commit -m "feat: _alpha_score 헬퍼 구현 및 cooking_service 뼈대 추가"
```

---

### Task 4: `cook_recipe` — 404 + 빈 ingredients 처리

**Files:**
- Modify: `app/services/cooking_service.py`
- Test: `tests/test_cooking_service.py` (추가)

- [ ] **Step 1: 테스트 추가**

`tests/test_cooking_service.py` 파일 끝에 추가:

```python
# ─── cook_recipe service tests ─────────────────────────────────────

from app.services.cooking_service import cook_recipe


def _make_recipe(recipe_id=7, name="닭볶음탕"):
    from unittest.mock import MagicMock
    r = MagicMock()
    r.id = recipe_id
    r.name = name
    return r


@pytest.mark.asyncio
async def test_cook_recipe_recipe_not_found(mock_db, mock_redis):
    from fastapi import HTTPException
    mock_db.get = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await cook_recipe(mock_db, mock_redis, "user1", 9999, CookRequest(ingredients=[]))

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_cook_recipe_empty_ingredients_skips_db(mock_db, mock_redis):
    recipe = _make_recipe()
    mock_db.get = AsyncMock(return_value=recipe)
    mock_db.commit = AsyncMock()

    result = await cook_recipe(mock_db, mock_redis, "user1", 7, CookRequest(ingredients=[]))

    assert result.recipe_id == 7
    assert result.recipe_name == "닭볶음탕"
    assert result.deductions == []
    mock_db.commit.assert_not_called()
```

- [ ] **Step 2: 실패 확인**

```bash
python -m pytest tests/test_cooking_service.py -v --tb=short -q -k "not (alpha or schema or deduction)"
```

Expected: `NotImplementedError`

- [ ] **Step 3: 해당 케이스 구현**

`cook_recipe` 함수를 아래로 교체:

```python
async def cook_recipe(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    recipe_id: int,
    data: CookRequest,
) -> CookResult:
    recipe = await db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if not data.ingredients:
        return CookResult(recipe_id=recipe_id, recipe_name=recipe.name, deductions=[])

    raise NotImplementedError  # Task 5에서 구현
```

- [ ] **Step 4: 통과 확인**

```bash
python -m pytest tests/test_cooking_service.py -v --tb=short -q -k "not_found or empty"
```

Expected: 2개 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/services/cooking_service.py tests/test_cooking_service.py
git commit -m "feat: cook_recipe 404 및 빈 ingredients 처리 구현"
```

---

### Task 5: `cook_recipe` — α-스코어 차감 알고리즘 전체 구현

**Files:**
- Modify: `app/services/cooking_service.py`
- Test: `tests/test_cooking_service.py` (추가)

- [ ] **Step 1: 차감 로직 테스트 추가**

`tests/test_cooking_service.py` 파일 끝에 추가:

```python
# ─── Deduction logic tests ─────────────────────────────────────────

def _make_im(mid=5, name="닭가슴살", risk_factor="3", bit_id=42):
    im = MagicMock()
    im.id = mid
    im.name = name
    im.risk_factor = Decimal(risk_factor)
    im.bit_id = bit_id
    return im


def _make_inv(item_id=10, user_id="user1", mid=5, quantity="200", days=3):
    item = MagicMock()
    item.id = item_id
    item.user_id = user_id
    item.ingredient_master_id = mid
    item.quantity = Decimal(quantity)
    item.expire_date = date.today() + timedelta(days=days)
    return item


def _db_result(rows):
    """db.execute()가 반환하는 결과 객체 목업."""
    r = MagicMock()
    r.scalars.return_value.all.return_value = rows
    return r


@pytest.mark.asyncio
async def test_cook_recipe_single_row_full_deduction(mock_db, mock_redis):
    """200g 요청, 200g 재고 1행 → 행 삭제 + 비트 클리어."""
    recipe = _make_recipe()
    im = _make_im()
    item = _make_inv(item_id=10, quantity="200", days=3)

    mock_db.get = AsyncMock(return_value=recipe)
    mock_db.execute = AsyncMock(side_effect=[_db_result([im]), _db_result([item])])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_redis.get = AsyncMock(return_value=(0).to_bytes(54, "big"))
    mock_redis.set = AsyncMock()

    result = await cook_recipe(
        mock_db, mock_redis, "user1", 7,
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=200.0)]),
    )

    assert result.recipe_id == 7
    d = result.deductions[0]
    assert d.ingredient_master_id == 5
    assert d.requested == 200.0
    assert d.deducted == 200.0
    assert len(d.rows_affected) == 1
    assert d.rows_affected[0].inventory_id == 10
    assert d.rows_affected[0].deducted == 200.0
    assert d.rows_affected[0].deleted is True
    mock_db.delete.assert_called_once_with(item)
    mock_redis.set.assert_called_once()  # 재고 소진 → 비트 클리어


@pytest.mark.asyncio
async def test_cook_recipe_alpha_order_sooner_expiry_first(mock_db, mock_redis):
    """item1(7일), item2(1일) 순서로 전달해도 item2부터 차감."""
    recipe = _make_recipe()
    im = _make_im()
    item1 = _make_inv(item_id=10, quantity="100", days=7)  # α낮음
    item2 = _make_inv(item_id=11, quantity="100", days=1)  # α높음

    mock_db.get = AsyncMock(return_value=recipe)
    # DB는 item1, item2 순서로 반환 (정렬 전)
    mock_db.execute = AsyncMock(side_effect=[_db_result([im]), _db_result([item1, item2])])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_redis.get = AsyncMock(return_value=(0).to_bytes(54, "big"))
    mock_redis.set = AsyncMock()

    result = await cook_recipe(
        mock_db, mock_redis, "user1", 7,
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=120.0)]),
    )

    d = result.deductions[0]
    assert d.deducted == 120.0
    # item2(1일, α높음) 먼저 전량 소진
    assert d.rows_affected[0].inventory_id == 11
    assert d.rows_affected[0].deducted == 100.0
    assert d.rows_affected[0].deleted is True
    # item1(7일)에서 나머지 20g 차감
    assert d.rows_affected[1].inventory_id == 10
    assert d.rows_affected[1].deducted == 20.0
    assert d.rows_affected[1].deleted is False
    # item1에 80g 잔여 → 비트 클리어 없음
    mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_cook_recipe_partial_deduction_insufficient_stock(mock_db, mock_redis):
    """100g 요청, 60g 재고 → 60g 차감 후 완전 소진 → 비트 클리어."""
    recipe = _make_recipe()
    im = _make_im()
    item = _make_inv(item_id=10, quantity="60", days=3)

    mock_db.get = AsyncMock(return_value=recipe)
    mock_db.execute = AsyncMock(side_effect=[_db_result([im]), _db_result([item])])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_redis.get = AsyncMock(return_value=(0).to_bytes(54, "big"))
    mock_redis.set = AsyncMock()

    result = await cook_recipe(
        mock_db, mock_redis, "user1", 7,
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=100.0)]),
    )

    d = result.deductions[0]
    assert d.requested == 100.0
    assert d.deducted == 60.0  # 보유량만 차감
    assert d.rows_affected[0].deleted is True
    mock_redis.set.assert_called_once()  # 재고 완전 소진


@pytest.mark.asyncio
async def test_cook_recipe_no_inventory_for_ingredient(mock_db, mock_redis):
    """해당 재료 재고 없음 → deducted=0, 비트 클리어 없음."""
    recipe = _make_recipe()
    im = _make_im()

    mock_db.get = AsyncMock(return_value=recipe)
    mock_db.execute = AsyncMock(side_effect=[_db_result([im]), _db_result([])])
    mock_db.commit = AsyncMock()
    mock_redis.set = AsyncMock()

    result = await cook_recipe(
        mock_db, mock_redis, "user1", 7,
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=100.0)]),
    )

    d = result.deductions[0]
    assert d.deducted == 0.0
    assert d.rows_affected == []
    mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_cook_recipe_multiple_ingredients(mock_db, mock_redis):
    """재료 2개 요청: 첫 번째 소진(비트 클리어), 두 번째 잔여 있음."""
    recipe = _make_recipe()
    im_a = _make_im(mid=5, name="닭가슴살", bit_id=42)
    im_b = _make_im(mid=12, name="양파", risk_factor="1", bit_id=10)
    item_a = _make_inv(item_id=10, mid=5, quantity="100", days=2)
    item_b = _make_inv(item_id=20, mid=12, quantity="200", days=5)

    mock_db.get = AsyncMock(return_value=recipe)
    mock_db.execute = AsyncMock(
        side_effect=[_db_result([im_a, im_b]), _db_result([item_a, item_b])]
    )
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_redis.get = AsyncMock(return_value=(0).to_bytes(54, "big"))
    mock_redis.set = AsyncMock()

    result = await cook_recipe(
        mock_db, mock_redis, "user1", 7,
        CookRequest(ingredients=[
            IngredientUsage(ingredient_master_id=5, quantity=100.0),   # 전량 소진
            IngredientUsage(ingredient_master_id=12, quantity=50.0),   # 150g 잔여
        ]),
    )

    assert len(result.deductions) == 2
    da = next(d for d in result.deductions if d.ingredient_master_id == 5)
    db_ = next(d for d in result.deductions if d.ingredient_master_id == 12)

    assert da.deducted == 100.0
    assert da.rows_affected[0].deleted is True

    assert db_.deducted == 50.0
    assert db_.rows_affected[0].deleted is False

    # 닭가슴살(42번 비트)만 클리어, 양파는 잔여 있으므로 set 1회
    assert mock_redis.set.call_count == 1
```

- [ ] **Step 2: 실패 확인**

```bash
python -m pytest tests/test_cooking_service.py -v --tb=short -q -k "deduction or ingredients or stock or inventory or alpha_order or multiple"
```

Expected: `NotImplementedError` 또는 AssertionError

- [ ] **Step 3: 전체 차감 알고리즘 구현**

`app/services/cooking_service.py`의 `cook_recipe`를 아래로 교체:

```python
async def cook_recipe(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    recipe_id: int,
    data: CookRequest,
) -> CookResult:
    recipe = await db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if not data.ingredients:
        return CookResult(recipe_id=recipe_id, recipe_name=recipe.name, deductions=[])

    requested_ids = [u.ingredient_master_id for u in data.ingredients]

    im_result = await db.execute(
        select(IngredientMaster).where(IngredientMaster.id.in_(requested_ids))
    )
    ingredient_masters: dict[int, IngredientMaster] = {
        im.id: im for im in im_result.scalars().all()
    }

    inv_result = await db.execute(
        select(UserInventory).where(
            UserInventory.user_id == user_id,
            UserInventory.ingredient_master_id.in_(requested_ids),
        )
    )
    all_items = inv_result.scalars().all()

    items_by_id: dict[int, list[UserInventory]] = defaultdict(list)
    for item in all_items:
        items_by_id[item.ingredient_master_id].append(item)

    deductions: list[IngredientDeductionResult] = []
    depleted: list[tuple[int, int]] = []  # (ingredient_master_id, bit_id)

    for usage in data.ingredients:
        mid = usage.ingredient_master_id
        im = ingredient_masters.get(mid)
        ingredient_name = im.name if im else str(mid)
        rf = float(im.risk_factor) if im else 1.0

        rows = list(items_by_id.get(mid, []))
        rows.sort(
            key=lambda r: _alpha_score(rf, float(r.quantity), r.expire_date),
            reverse=True,
        )

        remaining = float(usage.quantity)
        total_deducted = 0.0
        total_remaining = sum(float(r.quantity) for r in rows)
        rows_affected: list[InventoryDeduction] = []

        for row in rows:
            if remaining <= 0:
                break
            row_qty = float(row.quantity)
            if remaining >= row_qty:
                total_deducted += row_qty
                total_remaining -= row_qty
                remaining -= row_qty
                rows_affected.append(
                    InventoryDeduction(inventory_id=row.id, deducted=row_qty, deleted=True)
                )
                await db.delete(row)
            else:
                deducted = remaining
                total_deducted += deducted
                total_remaining -= deducted
                row.quantity = Decimal(str(round(row_qty - deducted, 10)))
                remaining = 0
                rows_affected.append(
                    InventoryDeduction(inventory_id=row.id, deducted=deducted, deleted=False)
                )

        if rows and total_remaining < 1e-9 and im is not None:
            depleted.append((mid, im.bit_id))

        deductions.append(
            IngredientDeductionResult(
                ingredient_master_id=mid,
                ingredient_name=ingredient_name,
                requested=float(usage.quantity),
                deducted=total_deducted,
                rows_affected=rows_affected,
            )
        )

    await db.commit()

    for _, bit_id in depleted:
        await clear_bit(redis, user_id, bit_id, db)

    return CookResult(
        recipe_id=recipe_id,
        recipe_name=recipe.name,
        deductions=deductions,
    )
```

- [ ] **Step 4: 전체 서비스 테스트 통과 확인**

```bash
python -m pytest tests/test_cooking_service.py -v --tb=short
```

Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/services/cooking_service.py tests/test_cooking_service.py
git commit -m "feat: cook_recipe 차감 알고리즘 구현 (α-스코어 정렬, 부분차감, 비트 클리어)"
```

---

### Task 6: 라우터 엔드포인트 및 HTTP 테스트

**Files:**
- Modify: `app/routers/recipes.py`
- Create: `tests/test_cooking_router.py`

- [ ] **Step 1: 라우터 테스트 파일 생성**

`tests/test_cooking_router.py` 생성:

```python
import pytest
from unittest.mock import patch, AsyncMock

from app.schemas.cooking import CookResult, IngredientDeductionResult, InventoryDeduction


def _make_cook_result(recipe_id=7, name="닭볶음탕") -> CookResult:
    return CookResult(
        recipe_id=recipe_id,
        recipe_name=name,
        deductions=[
            IngredientDeductionResult(
                ingredient_master_id=5,
                ingredient_name="닭가슴살",
                requested=200.0,
                deducted=200.0,
                rows_affected=[
                    InventoryDeduction(inventory_id=10, deducted=150.0, deleted=True),
                    InventoryDeduction(inventory_id=18, deducted=50.0, deleted=False),
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_cook_recipe_endpoint_success(real_client):
    mock_result = _make_cook_result()
    with patch("app.routers.recipes.cook_recipe", AsyncMock(return_value=mock_result)):
        resp = await real_client.post(
            "/api/v1/recipes/7/cook",
            json={"ingredients": [{"ingredient_master_id": 5, "quantity": 200.0}]},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["message"] == "요리가 완료되었습니다."
    assert body["data"]["recipe_id"] == 7
    assert body["data"]["recipe_name"] == "닭볶음탕"
    assert len(body["data"]["deductions"]) == 1
    d = body["data"]["deductions"][0]
    assert d["ingredient_master_id"] == 5
    assert d["requested"] == 200.0
    assert d["deducted"] == 200.0
    assert len(d["rows_affected"]) == 2
    assert d["rows_affected"][0]["deleted"] is True
    assert d["rows_affected"][1]["deleted"] is False


@pytest.mark.asyncio
async def test_cook_recipe_endpoint_not_found(real_client):
    from fastapi import HTTPException
    with patch(
        "app.routers.recipes.cook_recipe",
        AsyncMock(side_effect=HTTPException(status_code=404, detail="Recipe not found")),
    ):
        resp = await real_client.post(
            "/api/v1/recipes/9999/cook",
            json={"ingredients": []},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cook_recipe_endpoint_empty_ingredients(real_client):
    mock_result = CookResult(recipe_id=7, recipe_name="닭볶음탕", deductions=[])
    with patch("app.routers.recipes.cook_recipe", AsyncMock(return_value=mock_result)):
        resp = await real_client.post(
            "/api/v1/recipes/7/cook",
            json={"ingredients": []},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["deductions"] == []


@pytest.mark.asyncio
async def test_cook_recipe_endpoint_rejects_duplicate_ingredient(real_client):
    """Pydantic 검증: 중복 ingredient_master_id → 422 Unprocessable Entity."""
    with patch("app.routers.recipes.cook_recipe", AsyncMock()) as mock_cook:
        resp = await real_client.post(
            "/api/v1/recipes/7/cook",
            json={"ingredients": [
                {"ingredient_master_id": 5, "quantity": 100.0},
                {"ingredient_master_id": 5, "quantity": 50.0},
            ]},
        )

    assert resp.status_code == 422
    mock_cook.assert_not_called()


@pytest.mark.asyncio
async def test_cook_recipe_endpoint_rejects_zero_quantity(real_client):
    """Pydantic 검증: quantity=0 → 422."""
    with patch("app.routers.recipes.cook_recipe", AsyncMock()) as mock_cook:
        resp = await real_client.post(
            "/api/v1/recipes/7/cook",
            json={"ingredients": [{"ingredient_master_id": 5, "quantity": 0}]},
        )

    assert resp.status_code == 422
    mock_cook.assert_not_called()
```

- [ ] **Step 2: 실패 확인**

```bash
python -m pytest tests/test_cooking_router.py -v --tb=short -q
```

Expected: `405 Method Not Allowed` 또는 `404 Not Found` (엔드포인트 미존재)

- [ ] **Step 3: 엔드포인트 추가**

`app/routers/recipes.py` 상단 import 블록에 추가:

```python
from app.schemas.cooking import CookRequest, CookResult
from app.services.cooking_service import cook_recipe
```

그리고 파일 끝에 엔드포인트 추가:

```python
@router.post(
    "/{recipe_id}/cook",
    response_model=ApiResponse[CookResult],
    status_code=200,
    summary="요리 완료 처리",
    description=(
        "레시피를 채택하여 요리를 완료합니다.\n\n"
        "- `ingredients`에 포함된 재료만 차감 (레시피에 있어도 목록 미포함 시 차감 안 함)\n"
        "- α-스코어 내림차순으로 재고 우선 차감 (유통기한 임박·수량 많은 항목 먼저)\n"
        "- 재고 부족 시 보유량만큼 부분 차감 (`deducted < requested`)\n"
        "- 재고 완전 소진 시 Redis BitSet 해당 비트 자동 클리어\n\n"
        "**Bearer 토큰 필수.**"
    ),
    responses={
        **_AUTH_401,
        404: {"description": "존재하지 않는 recipe_id"},
    },
    openapi_extra=_BEARER,
)
async def cook_recipe_endpoint(
    recipe_id: int,
    data: CookRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    result = await cook_recipe(db, redis, user_id, recipe_id, data)
    return ApiResponse(success=True, data=result, message="요리가 완료되었습니다.")
```

- [ ] **Step 4: 전체 테스트 통과 확인**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: 모든 테스트 PASS (CI 환경에서 실제 DB 테스트는 skip)

- [ ] **Step 5: 커밋**

```bash
git add app/routers/recipes.py tests/test_cooking_router.py
git commit -m "feat: POST /recipes/{recipe_id}/cook 엔드포인트 추가"
```

---

## 완료 체크리스트

- [ ] `app/schemas/cooking.py` — 5개 Pydantic 클래스 (IngredientUsage, CookRequest, InventoryDeduction, IngredientDeductionResult, CookResult)
- [ ] `app/services/cooking_service.py` — `_alpha_score` + `cook_recipe`
- [ ] `app/routers/recipes.py` — `POST /{recipe_id}/cook` 엔드포인트
- [ ] `tests/test_cooking_service.py` — 스키마 검증 4개 + α-스코어 4개 + 서비스 7개 = 15개 테스트
- [ ] `tests/test_cooking_router.py` — HTTP 라우터 5개 테스트
- [ ] 전체 테스트 PASS 확인
