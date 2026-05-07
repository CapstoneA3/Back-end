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

    find_result = MagicMock()
    find_result.scalar_one_or_none.return_value = ing
    mock_db.execute = AsyncMock(return_value=find_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    def _refresh_side_effect(obj):
        obj.id = item.id
        obj.created_at = item.created_at
        obj.ingredient = ing

    mock_db.refresh = AsyncMock(side_effect=_refresh_side_effect)

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


# ── delete_ingredient 테스트 ──────────────────────────────

async def test_delete_inventory_last_item_clears_bit(mock_db, mock_redis):
    """마지막 항목 삭제 시 Redis bit가 clear되어야 한다."""
    from app.services.inventory_service import delete_inventory_item

    ing = _make_ingredient(bit_id=5)
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(side_effect=[item, ing])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    mock_db.execute = AsyncMock(return_value=count_result)

    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    await delete_inventory_item(mock_db, mock_redis, "user1", 10)

    mock_db.delete.assert_called_once_with(item)
    mock_db.commit.assert_called_once()
    mock_redis.set.assert_called_once()  # bit clear 호출됨


async def test_delete_inventory_missing_master_does_not_raise(mock_db, mock_redis):
    """remaining==0이지만 IngredientMaster가 없어도 예외 없이 완료되어야 한다."""
    from app.services.inventory_service import delete_inventory_item

    ing = _make_ingredient(bit_id=5)
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(side_effect=[item, None])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    mock_db.execute = AsyncMock(return_value=count_result)

    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    await delete_inventory_item(mock_db, mock_redis, "user1", 10)

    mock_redis.set.assert_not_called()  # ingredient 없으면 bit clear 안 함


async def test_delete_inventory_remaining_items_keep_bit(mock_db, mock_redis):
    """같은 재료 항목이 남아있으면 bit를 clear하지 않아야 한다."""
    from app.services.inventory_service import delete_inventory_item

    ing = _make_ingredient(bit_id=5)
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(return_value=item)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    mock_db.execute = AsyncMock(return_value=count_result)

    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    await delete_inventory_item(mock_db, mock_redis, "user1", 10)

    mock_db.delete.assert_called_once_with(item)
    mock_db.commit.assert_called_once()
    mock_redis.set.assert_not_called()  # bit clear 호출 안 됨


async def test_delete_inventory_not_found(mock_db, mock_redis):
    """존재하지 않는 inventory_id → 404."""
    from app.services.inventory_service import delete_inventory_item
    from fastapi import HTTPException

    mock_db.get = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await delete_inventory_item(mock_db, mock_redis, "user1", 9999)
    assert exc.value.status_code == 404


async def test_delete_inventory_forbidden(mock_db, mock_redis):
    """다른 유저의 항목 삭제 시도 → 403."""
    from app.services.inventory_service import delete_inventory_item
    from fastapi import HTTPException

    ing = _make_ingredient()
    item = _make_inventory_item(ing)  # user_id = "user1"

    mock_db.get = AsyncMock(return_value=item)

    with pytest.raises(HTTPException) as exc:
        await delete_inventory_item(mock_db, mock_redis, "other_user", 10)
    assert exc.value.status_code == 403


# ── DELETE /inventory/{id} 라우터 테스트 ─────────────────

async def test_delete_inventory_endpoint_success(client, mock_db, mock_redis):
    """정상 삭제 요청 → 200, success=True."""
    ing = _make_ingredient(bit_id=5)
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(side_effect=[item, ing])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    mock_db.execute = AsyncMock(return_value=count_result)

    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    resp = await client.delete("/api/v1/inventory/10", headers={"X-User-ID": "user1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["message"] == "재료가 삭제되었습니다."
    assert body["data"] is None   # ← add this line


async def test_delete_inventory_endpoint_not_found(client, mock_db, mock_redis):
    """존재하지 않는 inventory_id → HTTP 404."""
    mock_db.get = AsyncMock(return_value=None)
    resp = await client.delete("/api/v1/inventory/9999", headers={"X-User-ID": "user1"})
    assert resp.status_code == 404


async def test_delete_inventory_endpoint_forbidden(client, mock_db, mock_redis):
    """다른 유저의 항목 삭제 → HTTP 403."""
    ing = _make_ingredient()
    item = _make_inventory_item(ing)  # item.user_id == "user1"
    mock_db.get = AsyncMock(return_value=item)
    resp = await client.delete("/api/v1/inventory/10", headers={"X-User-ID": "other_user"})
    assert resp.status_code == 403


async def test_delete_inventory_endpoint_requires_user_id(client):
    """X-User-ID 헤더 없으면 422."""
    resp = await client.delete("/api/v1/inventory/10")
    assert resp.status_code == 422
