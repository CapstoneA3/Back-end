from app.schemas.ingredient import IngredientMasterRead
from decimal import Decimal


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
