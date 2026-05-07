# Inventory Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `DELETE /api/v1/inventory/{inventory_id}` 엔드포인트를 추가하고, 마지막 항목 삭제 시 Redis bit를 자동으로 clear한다.

**Architecture:** DB에서 단건 삭제 후 동일 재료의 남은 개수를 확인한다. 잔여 개수가 0이면 `clear_bit`를 호출해 Redis BitSet을 갱신한다. DB 먼저, Redis 후처리 패턴으로 기존 `register_ingredient`와 일관성을 유지한다.

**Tech Stack:** FastAPI, SQLAlchemy async, Redis (`clear_bit` in `bitset_service.py`), pytest + AsyncMock

---

## File Map

| 파일 | 변경 |
|------|------|
| `app/services/inventory_service.py` | `delete_ingredient` 함수 추가, `func` · `clear_bit` import 추가 |
| `app/routers/inventory.py` | `DELETE /{inventory_id}` 엔드포인트 추가, `delete_ingredient` import |
| `tests/test_inventory.py` | 삭제 관련 테스트 6개 추가 |

---

### Task 1: `delete_ingredient` 서비스 함수

**Files:**
- Modify: `app/services/inventory_service.py`
- Test: `tests/test_inventory.py`

- [ ] **Step 1: 실패하는 테스트 4개 작성**

`tests/test_inventory.py` 하단에 추가:

```python
# ── delete_ingredient 테스트 ──────────────────────────────

async def test_delete_inventory_last_item_clears_bit(mock_db, mock_redis):
    """마지막 항목 삭제 시 Redis bit가 clear되어야 한다."""
    from app.services.inventory_service import delete_ingredient

    ing = _make_ingredient(bit_id=5)
    item = _make_inventory_item(ing)

    # db.get 첫 번째 호출: UserInventory 반환, 두 번째: IngredientMaster 반환
    mock_db.get = AsyncMock(side_effect=[item, ing])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    # COUNT 쿼리 → 0 (마지막 항목이었음)
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    mock_db.execute = AsyncMock(return_value=count_result)

    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    await delete_ingredient(mock_db, mock_redis, "user1", 10)

    mock_db.delete.assert_called_once_with(item)
    mock_db.commit.assert_called_once()
    mock_redis.set.assert_called_once()  # bit clear 호출됨


async def test_delete_inventory_remaining_items_keep_bit(mock_db, mock_redis):
    """같은 재료 항목이 남아있으면 bit를 clear하지 않아야 한다."""
    from app.services.inventory_service import delete_ingredient

    ing = _make_ingredient(bit_id=5)
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(return_value=item)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    # COUNT 쿼리 → 1 (다른 배치 남아있음)
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    mock_db.execute = AsyncMock(return_value=count_result)

    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    await delete_ingredient(mock_db, mock_redis, "user1", 10)

    mock_db.delete.assert_called_once_with(item)
    mock_redis.set.assert_not_called()  # bit clear 호출 안 됨


async def test_delete_inventory_not_found(mock_db, mock_redis):
    """존재하지 않는 inventory_id → 404."""
    from app.services.inventory_service import delete_ingredient
    from fastapi import HTTPException

    mock_db.get = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await delete_ingredient(mock_db, mock_redis, "user1", 9999)
    assert exc.value.status_code == 404


async def test_delete_inventory_forbidden(mock_db, mock_redis):
    """다른 유저의 항목 삭제 시도 → 403."""
    from app.services.inventory_service import delete_ingredient
    from fastapi import HTTPException

    ing = _make_ingredient()
    item = _make_inventory_item(ing)  # user_id = "user1"

    mock_db.get = AsyncMock(return_value=item)

    with pytest.raises(HTTPException) as exc:
        await delete_ingredient(mock_db, mock_redis, "other_user", 10)
    assert exc.value.status_code == 403
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```
pytest tests/test_inventory.py::test_delete_inventory_last_item_clears_bit tests/test_inventory.py::test_delete_inventory_remaining_items_keep_bit tests/test_inventory.py::test_delete_inventory_not_found tests/test_inventory.py::test_delete_inventory_forbidden -v
```

Expected: 4개 모두 `ImportError` 또는 `FAILED` (함수 미구현)

- [ ] **Step 3: `delete_ingredient` 구현**

`app/services/inventory_service.py` 상단 import 수정:

```python
from sqlalchemy import select, func
from app.services.bitset_service import set_bit, clear_bit
```

파일 하단에 추가 (기존 `get_dashboard` 다음):

```python
async def delete_ingredient(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    inventory_id: int,
) -> None:
    item = await db.get(UserInventory, inventory_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    if item.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    ingredient_master_id = item.ingredient_master_id
    await db.delete(item)
    await db.commit()

    result = await db.execute(
        select(func.count()).select_from(UserInventory).where(
            UserInventory.user_id == user_id,
            UserInventory.ingredient_master_id == ingredient_master_id,
        )
    )
    remaining = result.scalar()

    if remaining == 0:
        ingredient = await db.get(IngredientMaster, ingredient_master_id)
        await clear_bit(redis, user_id, ingredient.bit_id)
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```
pytest tests/test_inventory.py::test_delete_inventory_last_item_clears_bit tests/test_inventory.py::test_delete_inventory_remaining_items_keep_bit tests/test_inventory.py::test_delete_inventory_not_found tests/test_inventory.py::test_delete_inventory_forbidden -v
```

Expected: 4개 모두 `PASSED`

- [ ] **Step 5: 커밋**

```bash
git add app/services/inventory_service.py tests/test_inventory.py
git commit -m "feat: add delete_ingredient service with bit clear logic"
```

---

### Task 2: DELETE 라우터 엔드포인트

**Files:**
- Modify: `app/routers/inventory.py`
- Test: `tests/test_inventory.py`

- [ ] **Step 1: 실패하는 테스트 2개 작성**

`tests/test_inventory.py` 하단에 추가:

```python
# ── DELETE /inventory/{id} 라우터 테스트 ─────────────────

async def test_delete_inventory_endpoint_success(client, mock_db, mock_redis):
    """정상 삭제 요청 → 200, success=True."""
    ing = _make_ingredient(bit_id=5)
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(side_effect=[item, ing])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    count_result = MagicMock()
    count_result.scalar.return_value = 0
    mock_db.execute = AsyncMock(return_value=count_result)

    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    resp = await client.delete("/api/v1/inventory/10", headers={"X-User-ID": "user1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["message"] == "재료가 삭제되었습니다."


async def test_delete_inventory_endpoint_requires_user_id(client):
    """X-User-ID 헤더 없으면 422."""
    resp = await client.delete("/api/v1/inventory/10")
    assert resp.status_code == 422
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```
pytest tests/test_inventory.py::test_delete_inventory_endpoint_success tests/test_inventory.py::test_delete_inventory_endpoint_requires_user_id -v
```

Expected: 2개 모두 `FAILED` (404 — 라우터 미등록)

- [ ] **Step 3: 라우터 엔드포인트 구현**

`app/routers/inventory.py` import 줄 수정:

```python
from app.services.inventory_service import register_ingredient, get_dashboard, delete_ingredient
```

파일 하단에 추가:

```python
@router.delete("/{inventory_id}", response_model=ApiResponse[None], status_code=200)
async def delete_inventory(
    inventory_id: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    await delete_ingredient(db, redis, user_id, inventory_id)
    return ApiResponse(success=True, data=None, message="재료가 삭제되었습니다.")
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

```
pytest tests/test_inventory.py -v
```

Expected: 전체 10개 모두 `PASSED`

- [ ] **Step 5: 커밋**

```bash
git add app/routers/inventory.py tests/test_inventory.py
git commit -m "feat: add DELETE /inventory/{inventory_id} endpoint"
```
