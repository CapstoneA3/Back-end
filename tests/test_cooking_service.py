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
