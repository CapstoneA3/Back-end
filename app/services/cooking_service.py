from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from app.models.recipe import Recipe
from app.models.inventory import UserInventory
from app.models.ingredient import IngredientMaster
from app.schemas.cooking import (
    CookRequest,
    CookResult,
    IngredientDeductionResult,
    InventoryDeduction,
)
from app.services.bitset_service import clear_bit


def _alpha_score(risk_factor: float, quantity: float, expire_date: date) -> float:
    """α-스코어: 높을수록 먼저 차감. D-day² 분모로 임박 재료 우선."""
    days_left = max(1, (expire_date - date.today()).days)
    return risk_factor * quantity / (days_left ** 2 + 1)


async def cook_recipe(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    recipe_id: int,
    data: CookRequest,
) -> CookResult:
    recipe = await db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if not data.ingredients:
        return CookResult(recipe_id=recipe_id, recipe_name=recipe.name, deductions=[])

    raise NotImplementedError  # Task 5에서 구현
