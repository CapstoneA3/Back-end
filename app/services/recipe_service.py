from collections import defaultdict
from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import redis.asyncio as aioredis

from app.models.recipe import Recipe, RecipeIngredient, RecipeStep
from app.models.inventory import UserInventory
from app.schemas.recipe import (
    RecipeIngredientRead,
    RecipeStepRead,
    RecipeRecommendItem,
    RecipeRecommendList,
    RecipeDetailRead,
)
from app.services.bitset_service import get_user_bitset


def _calc_score(risk_factor: float, quantity: float, expire_date: date) -> float:
    days_left = max(1, (expire_date - date.today()).days)
    return risk_factor * quantity / (days_left ** 2 + 1)


def _filter_by_bitset(
    user_bitset: int,
    masks: list[Optional[int]],
) -> list[bool]:
    result = []
    for mask in masks:
        if mask is None:
            result.append(False)
            continue
        m = int(mask)
        result.append(m != 0 and (user_bitset & m) == m)
    return result


def _score_recipe(
    recipe_ingredients: list,
    inv_lookup: dict[int, list[tuple[float, date, float]]],
) -> float:
    total = 0.0
    for ri in recipe_ingredients:
        if ri.ingredient_master_id is None:
            continue
        for qty, exp_date, rf in inv_lookup.get(ri.ingredient_master_id, []):
            total += _calc_score(rf, qty, exp_date)
    return total
