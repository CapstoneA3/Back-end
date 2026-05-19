import pytest
from unittest.mock import MagicMock, AsyncMock
from decimal import Decimal
from datetime import date, timedelta, datetime


def _make_ingredient(bit_id=5, default_shelf_days=7):
    ing = MagicMock()
    ing.id = 1
    ing.bit_id = bit_id
    ing.name = "?묓뙆"
    ing.category = "梨꾩냼"
    ing.default_shelf_days = default_shelf_days
    ing.risk_factor = Decimal("1")
    return ing


def _make_inventory_item(ingredient):
    item = MagicMock()
    item.id = 10
    item.user_id = "user1"
    item.ingredient_master_id = ingredient.id
    item.quantity = Decimal("2")
    item.unit = "媛?
    item.expire_date = date.today() + timedelta(days=7)
    item.created_at = datetime.now()
    item.ingredient = ingredient
    return item


async def test_post_inventory_registers_ingredient(client, mock_db):
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

    resp = await client.post(
        "/api/v1/inventory",
        json={"ingredient_master_id": 1, "quantity": "2", "unit": "媛?},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True


async def test_post_inventory_ingredient_not_found(client, mock_db):
    find_result = MagicMock()
    find_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=find_result)

    resp = await client.post(
        "/api/v1/inventory",
        json={"ingredient_master_id": 9999, "quantity": "1"},
    )
    assert resp.status_code == 404


async def test_get_inventory_dashboard(client, mock_db):
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


async def test_get_inventory_sorted_by_expire_date(client, mock_db):
    ing = _make_ingredient()
    item = _make_inventory_item(ing)

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [item]
    mock_db.execute = AsyncMock(return_value=list_result)

    resp = await client.get("/api/v1/inventory?sort=expire_date")
    assert resp.status_code == 200


<<<<<<< HEAD
async def test_get_inventory_empty(client, mock_db, mock_redis):
    """?ш퀬 0媛??좉퇋 ?좎? ??200, items=[], total=0 (NPE ?놁쓬 寃利?."""
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=list_result)

    resp = await client.get("/api/v1/inventory", headers={"X-User-ID": "new-user"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0


async def test_get_inventory_empty_sorted_by_expire_date(client, mock_db, mock_redis):
    """?ш퀬 0媛?+ sort=expire_date ??200, items=[], total=0."""
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=list_result)

    resp = await client.get(
        "/api/v1/inventory?sort=expire_date", headers={"X-User-ID": "new-user"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0


async def test_get_inventory_requires_user_id(client):
    resp = await client.get("/api/v1/inventory")
    assert resp.status_code == 422
=======
# ?? delete_inventory_item ?뚯뒪????????????????????????????????
>>>>>>> master

async def test_delete_inventory_item_success(mock_db):
    """?뺤긽 ??젣 ??db.delete + commit ?몄텧."""
    from app.services.inventory_service import delete_inventory_item

    ing = _make_ingredient()
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(return_value=item)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    await delete_inventory_item(mock_db, "user1", 10)

    mock_db.delete.assert_called_once_with(item)
    mock_db.commit.assert_called_once()


async def test_delete_inventory_not_found(mock_db):
    """議댁옱?섏? ?딅뒗 inventory_id ??404."""
    from app.services.inventory_service import delete_inventory_item
    from fastapi import HTTPException

    mock_db.get = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await delete_inventory_item(mock_db, "user1", 9999)
    assert exc.value.status_code == 404


async def test_delete_inventory_forbidden(mock_db):
    """?ㅻⅨ ?좎?????ぉ ??젣 ?쒕룄 ??403."""
    from app.services.inventory_service import delete_inventory_item
    from fastapi import HTTPException

    ing = _make_ingredient()
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(return_value=item)

    with pytest.raises(HTTPException) as exc:
        await delete_inventory_item(mock_db, "other_user", 10)
    assert exc.value.status_code == 403


# ?? DELETE /inventory/{id} ?쇱슦???뚯뒪???????????????????

async def test_delete_inventory_endpoint_success(client, mock_db):
    """?뺤긽 ??젣 ?붿껌 ??200, success=True."""
    ing = _make_ingredient()
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(return_value=item)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    resp = await client.delete("/api/v1/inventory/10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["message"] == "?щ즺媛 ??젣?섏뿀?듬땲??"
    assert body["data"] is None


async def test_delete_inventory_endpoint_not_found(client, mock_db):
    """議댁옱?섏? ?딅뒗 inventory_id ??HTTP 404."""
    mock_db.get = AsyncMock(return_value=None)
    resp = await client.delete("/api/v1/inventory/9999")
    assert resp.status_code == 404


async def test_delete_inventory_endpoint_forbidden(client, mock_db):
    """?ㅻⅨ ?좎? ?뚯쑀 ??ぉ ??젣 ??HTTP 403."""
    ing = _make_ingredient()
    item = _make_inventory_item(ing)
    item.user_id = "other_user"
    mock_db.get = AsyncMock(return_value=item)
    resp = await client.delete("/api/v1/inventory/10")
    assert resp.status_code == 403


# ?? update_inventory_item ?뚯뒪????????????????????????????

async def test_update_inventory_item_quantity(mock_db):
    """?섎웾留?蹂寃???DB 而ㅻ컠."""
    from app.services.inventory_service import update_inventory_item
    from app.schemas.inventory import InventoryUpdate

    ing = _make_ingredient()
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(return_value=item)
    mock_db.commit = AsyncMock()

    await update_inventory_item(mock_db, "user1", 10, InventoryUpdate(quantity=Decimal("5")))

    assert item.quantity == Decimal("5")
    mock_db.commit.assert_called_once()


async def test_update_inventory_item_unit_and_expire(mock_db):
    """?⑥쐞쨌?좏넻湲고븳 蹂寃???DB 而ㅻ컠."""
    from app.services.inventory_service import update_inventory_item
    from app.schemas.inventory import InventoryUpdate

    ing = _make_ingredient()
    item = _make_inventory_item(ing)
    new_date = date.today() + timedelta(days=14)

    mock_db.get = AsyncMock(return_value=item)
    mock_db.commit = AsyncMock()

    await update_inventory_item(mock_db, "user1", 10, InventoryUpdate(unit="g", expire_date=new_date))

    assert item.unit == "g"
    assert item.expire_date == new_date
    mock_db.commit.assert_called_once()


async def test_update_inventory_item_zero_quantity_deletes(mock_db):
    """?섎웾??0???섎㈃ ????젣."""
    from app.services.inventory_service import update_inventory_item
    from app.schemas.inventory import InventoryUpdate

    ing = _make_ingredient()
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(return_value=item)
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    await update_inventory_item(mock_db, "user1", 10, InventoryUpdate(quantity=Decimal("0")))

    mock_db.delete.assert_called_once_with(item)
    mock_db.commit.assert_called_once()


async def test_update_inventory_item_not_found(mock_db):
    """議댁옱?섏? ?딅뒗 inventory_id ??404."""
    from app.services.inventory_service import update_inventory_item
    from app.schemas.inventory import InventoryUpdate
    from fastapi import HTTPException

    mock_db.get = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await update_inventory_item(mock_db, "user1", 9999, InventoryUpdate(quantity=Decimal("2")))
    assert exc.value.status_code == 404


async def test_update_inventory_item_forbidden(mock_db):
    """?ㅻⅨ ?좎?????ぉ ?섏젙 ?쒕룄 ??403."""
    from app.services.inventory_service import update_inventory_item
    from app.schemas.inventory import InventoryUpdate
    from fastapi import HTTPException

    ing = _make_ingredient()
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(return_value=item)

    with pytest.raises(HTTPException) as exc:
        await update_inventory_item(mock_db, "other_user", 10, InventoryUpdate(quantity=Decimal("2")))
    assert exc.value.status_code == 403


async def test_update_inventory_item_no_fields_is_noop(mock_db):
    """蹂寃??꾨뱶 ?놁쓬 ??DB 而ㅻ컠留?"""
    from app.services.inventory_service import update_inventory_item
    from app.schemas.inventory import InventoryUpdate

    ing = _make_ingredient()
    item = _make_inventory_item(ing)
    original_qty = item.quantity

    mock_db.get = AsyncMock(return_value=item)
    mock_db.commit = AsyncMock()

    await update_inventory_item(mock_db, "user1", 10, InventoryUpdate())

    assert item.quantity == original_qty
    mock_db.commit.assert_called_once()


# ?? PATCH /inventory/{id} ?쇱슦???뚯뒪????????????????????

async def test_patch_inventory_endpoint_success(client, mock_db):
    """?섎웾 蹂寃??붿껌 ??200, success=True, data=None."""
    ing = _make_ingredient()
    item = _make_inventory_item(ing)

    mock_db.get = AsyncMock(return_value=item)
    mock_db.commit = AsyncMock()

    resp = await client.patch(
        "/api/v1/inventory/10",
        json={"quantity": "3"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] is None


async def test_patch_inventory_endpoint_not_found(client, mock_db):
    """議댁옱?섏? ?딅뒗 id ??404."""
    mock_db.get = AsyncMock(return_value=None)
    resp = await client.patch(
        "/api/v1/inventory/9999",
        json={"quantity": "1"},
    )
    assert resp.status_code == 404


async def test_patch_inventory_endpoint_forbidden(client, mock_db):
    """?ㅻⅨ ?좎? ?뚯쑀 ??ぉ ?섏젙 ??403."""
    ing = _make_ingredient()
    item = _make_inventory_item(ing)
    item.user_id = "other_user"
    mock_db.get = AsyncMock(return_value=item)
    resp = await client.patch(
        "/api/v1/inventory/10",
        json={"quantity": "1"},
    )
    assert resp.status_code == 403

