import redis.asyncio as aioredis

_TOTAL = 427
_BYTE_LEN = (_TOTAL + 7) // 8  # 54 bytes


def _key(user_id: str) -> str:
    return f"user:{user_id}:bitset"


async def get_user_bitset(redis: aioredis.Redis, user_id: str) -> int:
    val = await redis.get(_key(user_id))
    return int.from_bytes(val, "big") if val else 0


async def set_bit(redis: aioredis.Redis, user_id: str, bit_id: int) -> None:
    current = await get_user_bitset(redis, user_id)
    updated = current | (1 << bit_id)
    await redis.set(_key(user_id), updated.to_bytes(_BYTE_LEN, "big"))


async def clear_bit(redis: aioredis.Redis, user_id: str, bit_id: int) -> None:
    current = await get_user_bitset(redis, user_id)
    updated = current & ~(1 << bit_id)
    await redis.set(_key(user_id), updated.to_bytes(_BYTE_LEN, "big"))


async def has_bit(redis: aioredis.Redis, user_id: str, bit_id: int) -> bool:
    current = await get_user_bitset(redis, user_id)
    return bool(current & (1 << bit_id))
