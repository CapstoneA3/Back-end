from datetime import date, timedelta
import random

from simulate.data_gen import UserState, VirtualInventoryItem
from simulate.engine import (
    build_bitset,
    parse_quantity,
    expire_check,
    fifo_deduct,
    replenish,
)


def _item(
    mid: int = 1,
    bit_id: int = 0,
    qty: float = 100.0,
    days: int = 5,
    category: str = "채소",
    risk_factor: float = 1.0,
) -> VirtualInventoryItem:
    today = date.today()
    return VirtualInventoryItem(
        ingredient_master_id=mid,
        name=f"재료{mid}",
        category=category,
        bit_id=bit_id,
        risk_factor=risk_factor,
        quantity=qty,
        registered_date=today,
        expire_date=today + timedelta(days=days),
    )


def _state(*items: VirtualInventoryItem) -> UserState:
    return UserState(user_id=1, inventory=list(items))


# ── build_bitset ───────────────────────────────────────────────────────────────

def test_build_bitset_single():
    assert build_bitset([_item(bit_id=3)]) == (1 << 3)


def test_build_bitset_multiple():
    assert build_bitset([_item(bit_id=0), _item(bit_id=2)]) == (1 << 0) | (1 << 2)


def test_build_bitset_empty():
    assert build_bitset([]) == 0


# ── parse_quantity ─────────────────────────────────────────────────────────────

def test_parse_quantity_integer_string():
    assert parse_quantity("2") == 2.0


def test_parse_quantity_float_string():
    assert abs(parse_quantity("100.5") - 100.5) < 1e-9


def test_parse_quantity_korean_fallback():
    assert parse_quantity("적당량") == 100.0


def test_parse_quantity_none_fallback():
    assert parse_quantity(None) == 100.0


# ── expire_check ───────────────────────────────────────────────────────────────

def test_expire_check_removes_expired():
    state = _state(_item(days=-1), _item(days=3))
    expire_check(state, date.today())
    assert len(state.inventory) == 1
    assert state.inventory[0].expire_date > date.today()


def test_expire_check_records_waste_quantity():
    state = _state(_item(days=-1, qty=200.0))
    expire_check(state, date.today())
    assert state.total_wasted == 200.0
    assert state.wasted_by_day == [200.0]


def test_expire_check_records_category_waste():
    state = _state(_item(days=-1, qty=150.0, category="육류"))
    expire_check(state, date.today())
    assert state.wasted_by_category["육류"] == 150.0


def test_expire_check_no_expired_appends_zero():
    state = _state(_item(days=5))
    expire_check(state, date.today())
    assert state.wasted_by_day == [0.0]
    assert state.total_wasted == 0.0


# ── fifo_deduct ────────────────────────────────────────────────────────────────

def test_fifo_deduct_consumes_oldest_first():
    today = date.today()
    old = VirtualInventoryItem(
        ingredient_master_id=1, name="재료1", category="채소",
        bit_id=0, risk_factor=1.0, quantity=50.0,
        registered_date=today, expire_date=today + timedelta(days=1),
    )
    fresh = VirtualInventoryItem(
        ingredient_master_id=1, name="재료1", category="채소",
        bit_id=0, risk_factor=1.0, quantity=50.0,
        registered_date=today, expire_date=today + timedelta(days=5),
    )
    state = UserState(user_id=1, inventory=[fresh, old])
    recipe = {"ingredients": [{"ingredient_master_id": 1, "quantity": "50"}]}
    fifo_deduct(state, recipe, today)
    # old batch 소진, fresh 남아야 함
    assert len(state.inventory) == 1
    assert state.inventory[0].expire_date == today + timedelta(days=5)


def test_fifo_deduct_partial():
    state = _state(_item(mid=1, qty=100.0))
    recipe = {"ingredients": [{"ingredient_master_id": 1, "quantity": "30"}]}
    fifo_deduct(state, recipe, date.today())
    assert abs(state.inventory[0].quantity - 70.0) < 1e-9


def test_fifo_deduct_skips_missing_ingredient():
    state = _state(_item(mid=1))
    recipe = {"ingredients": [{"ingredient_master_id": 99, "quantity": "50"}]}
    fifo_deduct(state, recipe, date.today())
    assert len(state.inventory) == 1


# ── replenish ──────────────────────────────────────────────────────────────────

def test_replenish_adds_items_on_day_7():
    masters = [
        {"id": i, "name": f"재료{i}", "category": "채소",
         "bit_id": i, "default_shelf_days": 10, "risk_factor": 1.0}
        for i in range(5)
    ]
    state = _state()
    rng = random.Random(0)
    before = len(state.inventory)
    replenish(state, sim_day=7, ingredient_master=masters, rng=rng)
    assert len(state.inventory) > before


def test_replenish_skips_non_multiple_of_7():
    masters = [{"id": 0, "name": "재료0", "category": "채소",
                "bit_id": 0, "default_shelf_days": 10, "risk_factor": 1.0}]
    state = _state()
    rng = random.Random(0)
    replenish(state, sim_day=3, ingredient_master=masters, rng=rng)
    assert len(state.inventory) == 0
