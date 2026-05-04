from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis
from fastapi import HTTPException
from app.models.ingredient import IngredientMaster
from app.models.inventory import UserInventory
from app.schemas.inventory import InventoryCreate
from app.services.bitset_service import set_bit


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

    expire_date = data.expire_date or (date.today() + timedelta(days=ingredient.default_shelf_days))
    unit = data.unit or "개"

    item = UserInventory(
        user_id=user_id,
        ingredient_master_id=data.ingredient_master_id,
        quantity=data.quantity,
        unit=unit,
        expire_date=expire_date,
    )
    item.ingredient = ingredient  # relationship 미리 세팅 (lazy="raise" 우회)
    db.add(item)
    await db.commit()
    await db.refresh(item)

    await set_bit(redis, user_id, ingredient.bit_id)
    return item
