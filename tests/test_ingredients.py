from app.schemas.ingredient import IngredientMasterRead
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


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
