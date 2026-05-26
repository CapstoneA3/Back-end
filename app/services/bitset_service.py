import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

_TOTAL = 427
_BYTE_LEN = (_TOTAL + 7) // 8  # 54 bytes


def _key(user_id: str) -> str:
    return f"user:{user_id}:bitset"


async def get_user_bitset(redis: aioredis.Redis, user_id: str) -> int:
    val = await redis.get(_key(user_id))
    return int.from_bytes(val, "big") if val else 0


async def rebuild_user_bitset(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: str,
) -> int:
    from app.models.inventory import UserInventory

    result = await db.execute(
        select(UserInventory)
        .where(UserInventory.user_id == user_id)
        .options(selectinload(UserInventory.ingredient))
    )
    items = result.scalars().all()

    mask = 0
    for item in items:
        mask |= (1 << item.ingredient.bit_id)

    await redis.set(_key(user_id), mask.to_bytes(_BYTE_LEN, "big"))
    return mask




async def _get_current(redis: aioredis.Redis, user_id: str, db: AsyncSession) -> int:
    val = await redis.get(_key(user_id))
    if val is not None:
        return int.from_bytes(val, "big")
    return await rebuild_user_bitset(db, redis, user_id)


async def set_bit(redis: aioredis.Redis, user_id: str, bit_id: int, db: AsyncSession) -> None:
    current = await _get_current(redis, user_id, db)
    updated = current | (1 << bit_id)
    await redis.set(_key(user_id), updated.to_bytes(_BYTE_LEN, "big"))


async def clear_bit(redis: aioredis.Redis, user_id: str, bit_id: int, db: AsyncSession) -> None:
    current = await _get_current(redis, user_id, db)
    updated = current & ~(1 << bit_id)
    await redis.set(_key(user_id), updated.to_bytes(_BYTE_LEN, "big"))


async def has_bit(redis: aioredis.Redis, user_id: str, bit_id: int) -> bool:
    current = await get_user_bitset(redis, user_id)
    return bool(current & (1 << bit_id))
