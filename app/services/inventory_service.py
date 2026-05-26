from datetime import date, timedelta
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
import redis.asyncio as aioredis
from app.models.ingredient import IngredientMaster
from app.models.inventory import UserInventory
from app.schemas.inventory import InventoryCreate, InventoryRead, InventoryDashboard, InventoryUpdate
from app.services.bitset_service import set_bit, clear_bit


async def register_ingredient(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    data: InventoryCreate,
) -> UserInventory:
    result = await db.execute(
        select(IngredientMaster).where(IngredientMaster.id == data.ingredient_master_id)
    )
    ingredient = result.scalar_one_or_none()
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    shelf_days = ingredient.default_shelf_days or 7
    expire_date = data.expire_date or (date.today() + timedelta(days=shelf_days))
    unit = data.unit or "개"

    item = UserInventory(
        user_id=user_id,
        ingredient_master_id=data.ingredient_master_id,
        quantity=data.quantity,
        unit=unit,
        expire_date=expire_date,
    )
    item.ingredient = ingredient
    db.add(item)
    await db.commit()
    await db.refresh(item)
    item.ingredient = ingredient  # refresh 후 관계 재할당 (lazy="raise" 우회)
    await set_bit(redis, user_id, ingredient.bit_id, db)
    return item


def _calc_score(risk_factor: float, quantity: float, expire_date: date) -> float:
    days_left = max(1, (expire_date - date.today()).days)
    return risk_factor * quantity / (days_left ** 2 + 1)


def _traffic_light(expire_date: date, risk_factor: float) -> Literal["red", "yellow", "green"]:
    """신호등 분류. 임계값 미확정 — 팀 내 확정 후 수정 필요."""
    days_left = (expire_date - date.today()).days
    if days_left <= 2 or (days_left <= 5 and risk_factor >= 2):
        return "red"
    if days_left <= 5 or (days_left <= 10 and risk_factor >= 2):
        return "yellow"
    return "green"


async def get_dashboard(
    db: AsyncSession,
    user_id: str,
    sort: str = "recommended",
) -> InventoryDashboard:
    result = await db.execute(
        select(UserInventory)
        .where(UserInventory.user_id == user_id)
        .options(selectinload(UserInventory.ingredient))
    )
    items = result.scalars().all()

    reads: list[InventoryRead] = []
    for item in items:
        rf = float(item.ingredient.risk_factor)
        score = _calc_score(rf, float(item.quantity), item.expire_date)
        tl = _traffic_light(item.expire_date, rf)
        reads.append(
            InventoryRead(
                id=item.id,
                user_id=item.user_id,
                ingredient_master_id=item.ingredient_master_id,
                quantity=item.quantity,
                unit=item.unit,
                expire_date=item.expire_date,
                created_at=item.created_at,
                ingredient=item.ingredient,
                traffic_light=tl,
                score=score,
            )
        )

    if sort == "expire_date":
        reads.sort(key=lambda x: x.expire_date)
    else:
        reads.sort(key=lambda x: x.score, reverse=True)

    return InventoryDashboard(items=reads, total=len(reads))


async def _clear_bit_if_last(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    ingredient_master_id: int,
) -> None:
    remaining = await db.execute(
        select(UserInventory).where(
            UserInventory.user_id == user_id,
            UserInventory.ingredient_master_id == ingredient_master_id,
        )
    )
    if remaining.scalars().first() is None:
        ingredient = await db.get(IngredientMaster, ingredient_master_id)
        if ingredient is not None:
            await clear_bit(redis, user_id, ingredient.bit_id, db)


async def delete_inventory_item(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    inventory_id: int,
) -> None:
    item = await db.get(UserInventory, inventory_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    if item.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    ingredient_master_id = item.ingredient_master_id
    await db.delete(item)
    await db.commit()
    await _clear_bit_if_last(db, redis, user_id, ingredient_master_id)


async def update_inventory_item(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
    inventory_id: int,
    data: InventoryUpdate,
) -> UserInventory:
    item = await db.get(UserInventory, inventory_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    if item.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if data.quantity is not None:
        if data.quantity == 0:
            ingredient_master_id = item.ingredient_master_id
            await db.delete(item)
            await db.commit()
            await _clear_bit_if_last(db, redis, user_id, ingredient_master_id)
            return item
        else:
            item.quantity = data.quantity

    if data.unit is not None:
        item.unit = data.unit
    if data.expire_date is not None:
        item.expire_date = data.expire_date

    await db.commit()
    return item
