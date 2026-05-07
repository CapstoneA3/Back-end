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

async def test_delete_inventory_item_deleted(mock_db):
    """항목 삭제 시 db.delete, db.commit이 호출되어야 한다."""
    from app.services.inventory_service import delete_ingredient

    ing = _make_ingredient(bit_id=5)
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(return_value=item)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    await delete_ingredient(mock_db, "user1", 10)

    mock_db.delete.assert_called_once_with(item)
    mock_db.commit.assert_called_once()


async def test_delete_inventory_not_found(mock_db):
    """존재하지 않는 inventory_id → 404."""
    from app.services.inventory_service import delete_ingredient
    from fastapi import HTTPException

    mock_db.get = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await delete_ingredient(mock_db, "user1", 9999)
    assert exc.value.status_code == 404


async def test_delete_inventory_forbidden(mock_db):
    """다른 유저의 항목 삭제 시도 → 403."""
    from app.services.inventory_service import delete_ingredient
    from fastapi import HTTPException

    ing = _make_ingredient()
    item = _make_inventory_item(ing)  # user_id = "user1"

    mock_db.get = AsyncMock(return_value=item)

    with pytest.raises(HTTPException) as exc:
        await delete_ingredient(mock_db, "other_user", 10)
    assert exc.value.status_code == 403


# ── DELETE /inventory/{id} 라우터 테스트 ─────────────────

async def test_delete_inventory_endpoint_success(client, mock_db):
    """정상 삭제 요청 → 200, success=True."""
    ing = _make_ingredient(bit_id=5)
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(return_value=item)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    resp = await client.delete("/api/v1/inventory/10", headers={"X-User-ID": "user1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["message"] == "재료가 삭제되었습니다."


async def test_delete_inventory_endpoint_requires_user_id(client):
    """X-User-ID 헤더 없으면 422."""
    resp = await client.delete("/api/v1/inventory/10")
    assert resp.status_code == 422
