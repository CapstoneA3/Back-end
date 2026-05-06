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
    )
    assert resp.status_code == 404


async def test_get_inventory_dashboard(client, mock_db, mock_redis):
    ing = _make_ingredient(bit_id=5, default_shelf_days=7)
    item = _make_inventory_item(ing)

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [item]
    mock_db.execute = AsyncMock(return_value=list_result)

    resp = await client.get("/api/v1/inventory")
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

    resp = await client.get("/api/v1/inventory?sort=expire_date")
    assert resp.status_code == 200
