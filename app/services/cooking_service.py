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

    requested_ids = [u.ingredient_master_id for u in data.ingredients]

    im_result = await db.execute(
        select(IngredientMaster).where(IngredientMaster.id.in_(requested_ids))
    )
    ingredient_masters: dict[int, IngredientMaster] = {
        im.id: im for im in im_result.scalars().all()
    }

    inv_result = await db.execute(
        select(UserInventory).where(
            UserInventory.user_id == user_id,
            UserInventory.ingredient_master_id.in_(requested_ids),
        )
    )
    all_items = inv_result.scalars().all()

    items_by_id: dict[int, list[UserInventory]] = defaultdict(list)
    for item in all_items:
        items_by_id[item.ingredient_master_id].append(item)

    deductions: list[IngredientDeductionResult] = []
    depleted: list[tuple[int, int]] = []  # (ingredient_master_id, bit_id)

    for usage in data.ingredients:
        mid = usage.ingredient_master_id
        im = ingredient_masters.get(mid)
        ingredient_name = im.name if im else str(mid)
        rf = float(im.risk_factor) if im else 1.0

        rows = list(items_by_id.get(mid, []))
        rows.sort(
            key=lambda r: _alpha_score(rf, float(r.quantity), r.expire_date),
            reverse=True,
        )

        remaining = float(usage.quantity)
        total_deducted = 0.0
        total_remaining = sum(float(r.quantity) for r in rows)
        rows_affected: list[InventoryDeduction] = []

        for row in rows:
            if remaining <= 0:
                break
            row_qty = float(row.quantity)
            if remaining >= row_qty:
                total_deducted += row_qty
                total_remaining -= row_qty
                remaining -= row_qty
                rows_affected.append(
                    InventoryDeduction(inventory_id=row.id, deducted=Decimal(str(round(row_qty, 10))), deleted=True)
                )
                await db.delete(row)
            else:
                deducted = remaining
                total_deducted += deducted
                total_remaining -= deducted
                row.quantity = Decimal(str(round(row_qty - deducted, 10)))
                remaining = 0
                rows_affected.append(
                    InventoryDeduction(inventory_id=row.id, deducted=Decimal(str(round(deducted, 10))), deleted=False)
                )

        if rows and total_remaining < 1e-9 and im is not None:
            depleted.append((mid, im.bit_id))

        deductions.append(
            IngredientDeductionResult(
                ingredient_master_id=mid,
                ingredient_name=ingredient_name,
                requested=usage.quantity,
                deducted=Decimal(str(round(total_deducted, 10))),
                rows_affected=rows_affected,
            )
        )

    await db.commit()

    for _, bit_id in depleted:
        await clear_bit(redis, user_id, bit_id, db)

    return CookResult(
        recipe_id=recipe_id,
        recipe_name=recipe.name,
        deductions=deductions,
    )
