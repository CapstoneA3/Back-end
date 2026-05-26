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
        IngredientUsage(ingredient_master_id=5, quantity=Decimal("200.0")),
    ])
    assert req.ingredients[0].quantity == Decimal("200.0")
    assert req.ingredients[0].ingredient_master_id == 5


def test_cook_request_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=Decimal("0.0"))])


def test_cook_request_rejects_negative_quantity():
    with pytest.raises(ValidationError):
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=Decimal("-10.0"))])


def test_cook_request_rejects_duplicate_ingredient():
    with pytest.raises(ValidationError):
        CookRequest(ingredients=[
            IngredientUsage(ingredient_master_id=5, quantity=Decimal("100.0")),
            IngredientUsage(ingredient_master_id=5, quantity=Decimal("50.0")),
        ])


def test_cook_request_empty_ingredients_ok():
    req = CookRequest(ingredients=[])
    assert req.ingredients == []


def test_cook_result_schema():
    result = CookResult(recipe_id=7, recipe_name="닭볶음탕", deductions=[])
    assert result.recipe_id == 7
    assert result.deductions == []


def test_inventory_deduction_schema():
    d = InventoryDeduction(inventory_id=10, deducted=Decimal("150.0"), deleted=True)
    assert d.deleted is True


def test_ingredient_deduction_result_schema():
    r = IngredientDeductionResult(
        ingredient_master_id=5,
        ingredient_name="닭가슴살",
        requested=Decimal("200.0"),
        deducted=Decimal("200.0"),
        rows_affected=[InventoryDeduction(inventory_id=10, deducted=Decimal("150.0"), deleted=True)],
    )
    assert r.deducted == Decimal("200.0")
    assert len(r.rows_affected) == 1


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
