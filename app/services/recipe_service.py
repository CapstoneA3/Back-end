from collections import defaultdict
from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import redis.asyncio as aioredis

from app.models.ingredient import IngredientMaster
from app.models.recipe import Recipe, RecipeIngredient, RecipeStep
from app.models.inventory import UserInventory
from app.schemas.recipe import (
    RecipeIngredientRead,
    RecipeStepRead,
    RecipeRecommendItem,
    RecipeRecommendList,
    RecipeDetailRead,
)
from app.services.bitset_service import rebuild_user_bitset


def _calc_score(risk_factor: float, quantity: float, expire_date: date) -> float:
    days_left = max(1, (expire_date - date.today()).days)
    return risk_factor * quantity / (days_left ** 2 + 1)


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


def _calc_match(
    user_bitset: int,
    recipe_bit: Optional[int],
) -> tuple[float, int]:
    """(match_rate, missing_count) 반환. recipe_bit가 없으면 (0.0, 0)."""
    if recipe_bit is None or recipe_bit == 0:
        return (0.0, 0)
    m = int(recipe_bit)
    total = bin(m).count("1")
    matched = bin(user_bitset & m).count("1")
    return (matched / total, total - matched)


async def get_recommended_recipes(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    limit: int = 20,
    min_match_rate: float = 0.8,
) -> RecipeRecommendList:
    raw = await redis.get(f"user:{user_id}:bitset")
    user_bitset = (
        int.from_bytes(raw, "big") if raw is not None
        else await rebuild_user_bitset(db, redis, user_id)
    )

    # ingredient_master_id → bit_id 조회 (부족 재료 판별용)
    im_result = await db.execute(select(IngredientMaster.id, IngredientMaster.bit_id))
    ing_bit_map: dict[int, int] = {row.id: row.bit_id for row in im_result}

    # 1. 전체 레시피 로드
    recipe_result = await db.execute(select(Recipe))
    all_recipes = recipe_result.scalars().all()

    # 2. 부분 매칭 필터링
    candidates: list[tuple[Recipe, float, int]] = []
    for recipe in all_recipes:
        match_rate, missing_count = _calc_match(user_bitset, recipe.recipe_bit)
        if match_rate >= min_match_rate:
            candidates.append((recipe, match_rate, missing_count))

    if not candidates:
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
    matched_ids = [r.id for r, _, _ in candidates]
    ri_result = await db.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id.in_(matched_ids))
    )
    all_ri = ri_result.scalars().all()

    ri_by_recipe: dict[int, list] = defaultdict(list)
    for ri in all_ri:
        ri_by_recipe[ri.recipe_id].append(ri)

    # 5. 스코어 계산 + 부족 재료 목록 구성 + 정렬
    scored: list[tuple[Recipe, float, int, list[str]]] = []
    for recipe, match_rate, missing_count in candidates:
        score = _score_recipe(ri_by_recipe[recipe.id], inv_lookup)
        missing_names = [
            ri.ingredient_name or "알 수 없음"
            for ri in ri_by_recipe[recipe.id]
            if ri.ingredient_master_id is not None
            and ing_bit_map.get(ri.ingredient_master_id) is not None
            and not (user_bitset & (1 << ing_bit_map[ri.ingredient_master_id]))
        ]
        scored.append((recipe, score, missing_count, missing_names))

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
            missing_count=missing_count,
            missing_ingredients=missing_names,
            ingredients=[
                RecipeIngredientRead.model_validate(ri)
                for ri in ri_by_recipe[recipe.id]
            ],
        )
        for rank, (recipe, score, missing_count, missing_names) in enumerate(scored, start=1)
    ]

    return RecipeRecommendList(items=items, total=len(items))


async def get_recipe_detail(db: AsyncSession, recipe_id: int) -> RecipeDetailRead:
    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    ri_result = await db.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id)
    )
    ingredients = ri_result.scalars().all()

    rs_result = await db.execute(
        select(RecipeStep)
        .where(RecipeStep.recipe_id == recipe_id)
        .order_by(RecipeStep.step_order)
    )
    steps = rs_result.scalars().all()

    return RecipeDetailRead(
        id=recipe.id,
        name=recipe.name,
        cook_time_min=recipe.cook_time_min,
        servings=recipe.servings,
        ingredients=[RecipeIngredientRead.model_validate(ri) for ri in ingredients],
        steps=[RecipeStepRead.model_validate(rs) for rs in steps],
    )
