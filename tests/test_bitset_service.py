import pytest
from unittest.mock import AsyncMock
from app.services.bitset_service import set_bit, clear_bit, get_user_bitset, has_bit

BYTE_LEN = (427 + 7) // 8  # 54 bytes


@pytest.fixture
def redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock()
    return r


async def test_set_bit_on_empty(redis):
    await set_bit(redis, "user1", 0)
    redis.set.assert_called_once()
    args = redis.set.call_args[0]
    stored = int.from_bytes(args[1], "big")
    assert stored & (1 << 0)


async def test_clear_bit(redis):
    initial = (1 << 5).to_bytes(BYTE_LEN, "big")
    redis.get = AsyncMock(return_value=initial)

    await clear_bit(redis, "user1", 5)
    args = redis.set.call_args[0]
    stored = int.from_bytes(args[1], "big")
    assert not (stored & (1 << 5))


async def test_has_bit_true(redis):
    initial = (1 << 3).to_bytes(BYTE_LEN, "big")
    redis.get = AsyncMock(return_value=initial)
    assert await has_bit(redis, "user1", 3) is True


async def test_has_bit_false(redis):
    assert await has_bit(redis, "user1", 3) is False


async def test_get_user_bitset_empty(redis):
    assert await get_user_bitset(redis, "user1") == 0
