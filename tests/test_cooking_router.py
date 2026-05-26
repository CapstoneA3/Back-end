import pytest
from decimal import Decimal
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
                requested=Decimal("200.0"),
                deducted=Decimal("200.0"),
                rows_affected=[
                    InventoryDeduction(inventory_id=10, deducted=Decimal("150.0"), deleted=True),
                    InventoryDeduction(inventory_id=18, deducted=Decimal("50.0"), deleted=False),
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_cook_recipe_endpoint_success(client):
    mock_result = _make_cook_result()
    with patch("app.routers.recipes.cook_recipe", AsyncMock(return_value=mock_result)):
        resp = await client.post(
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
    assert len(d["rows_affected"]) == 2
    assert d["rows_affected"][0]["deleted"] is True
    assert d["rows_affected"][1]["deleted"] is False


@pytest.mark.asyncio
async def test_cook_recipe_endpoint_not_found(client):
    from fastapi import HTTPException
    with patch(
        "app.routers.recipes.cook_recipe",
        AsyncMock(side_effect=HTTPException(status_code=404, detail="Recipe not found")),
    ):
        resp = await client.post(
            "/api/v1/recipes/9999/cook",
            json={"ingredients": []},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cook_recipe_endpoint_empty_ingredients(client):
    mock_result = CookResult(recipe_id=7, recipe_name="닭볶음탕", deductions=[])
    with patch("app.routers.recipes.cook_recipe", AsyncMock(return_value=mock_result)):
        resp = await client.post(
            "/api/v1/recipes/7/cook",
            json={"ingredients": []},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["deductions"] == []


@pytest.mark.asyncio
async def test_cook_recipe_endpoint_rejects_duplicate_ingredient(client):
    """Pydantic 검증: 중복 ingredient_master_id → 422 Unprocessable Entity."""
    with patch("app.routers.recipes.cook_recipe", AsyncMock()) as mock_cook:
        resp = await client.post(
            "/api/v1/recipes/7/cook",
            json={"ingredients": [
                {"ingredient_master_id": 5, "quantity": 100.0},
                {"ingredient_master_id": 5, "quantity": 50.0},
            ]},
        )

    assert resp.status_code == 422
    mock_cook.assert_not_called()


@pytest.mark.asyncio
async def test_cook_recipe_endpoint_rejects_zero_quantity(client):
    """Pydantic 검증: quantity=0 → 422."""
    with patch("app.routers.recipes.cook_recipe", AsyncMock()) as mock_cook:
        resp = await client.post(
            "/api/v1/recipes/7/cook",
            json={"ingredients": [{"ingredient_master_id": 5, "quantity": 0}]},
        )

    assert resp.status_code == 422
    mock_cook.assert_not_called()
