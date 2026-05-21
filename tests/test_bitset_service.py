import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.bitset_service import set_bit, clear_bit, get_user_bitset, has_bit

BYTE_LEN = (427 + 7) // 8  # 54 bytes


@pytest.fixture
def redis():
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.set = AsyncMock()
    return r


@pytest.fixture
def db():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


async def test_set_bit_on_empty(redis, db):
    # redis.get returns None → _get_current triggers rebuild (mask=0), then ORs bit 0
    await set_bit(redis, "user1", 0, db)
    # set is called twice: rebuild stores 0, then set_bit stores bit 0
    last_args = redis.set.call_args_list[-1][0]
    stored = int.from_bytes(last_args[1], "big")
    assert stored & (1 << 0)


async def test_clear_bit(redis, db):
    initial = (1 << 5).to_bytes(BYTE_LEN, "big")
    redis.get = AsyncMock(return_value=initial)  # key exists → no rebuild

    await clear_bit(redis, "user1", 5, db)
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
