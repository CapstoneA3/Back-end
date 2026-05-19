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


async def get_recommended_recipes(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    limit: int = 20,
) -> RecipeRecommendList:
    user_bitset = await get_user_bitset(redis, user_id)

    # 1. 전체 레시피 로드
    recipe_result = await db.execute(select(Recipe))
    all_recipes = recipe_result.scalars().all()

    # 2. BitSet 필터링 (recipe_bit은 _BitMaskToInt로 이미 int 변환됨)
    masks = [r.recipe_bit for r in all_recipes]
    flags = _filter_by_bitset(user_bitset, masks)
    matched = [r for r, ok in zip(all_recipes, flags) if ok]

    if not matched:
        return RecipeRecommendList(items=[], total=0)

    # 3. 사용자 인벤토리 로드 (α-스코어 계산용)
    inv_result = await db.execute(
        select(UserInventory)
        .where(UserInventory.user_id == user_id)
        .options(selectinload(UserInventory.ingredient))
    )
    user_items = inv_result.scalars().all()

    inv_lookup: dict[int, list[tuple[float, date, float]]] = defaultdict(list)
    for item in user_items:
        inv_lookup[item.ingredient_master_id].append((
            float(item.quantity),
            item.expire_date,
            float(item.ingredient.risk_factor),
        ))

    # 4. 매칭된 레시피 재료 일괄 로드 (N+1 방지)
    matched_ids = [r.id for r in matched]
    ri_result = await db.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id.in_(matched_ids))
    )
    all_ri = ri_result.scalars().all()

    ri_by_recipe: dict[int, list] = defaultdict(list)
    for ri in all_ri:
        ri_by_recipe[ri.recipe_id].append(ri)

    # 5. 스코어 계산 + 정렬
    scored = [
        (recipe, _score_recipe(ri_by_recipe[recipe.id], inv_lookup))
        for recipe in matched
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    scored = scored[:limit]

    # 6. 응답 조립
    items = [
        RecipeRecommendItem(
            id=recipe.id,
            name=recipe.name,
            cook_time_min=recipe.cook_time_min,
            servings=recipe.servings,
            score=score,
            rank=rank,
            ingredients=[
                RecipeIngredientRead.model_validate(ri)
                for ri in ri_by_recipe[recipe.id]
            ],
        )
        for rank, (recipe, score) in enumerate(scored, start=1)
    ]

    return RecipeRecommendList(items=items, total=len(items))
