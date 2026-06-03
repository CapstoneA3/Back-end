import random
from datetime import date
from simulate.data_gen import VirtualInventoryItem, UserState, generate_user

_SAMPLE_MASTERS = [
    {
        "id": i, "name": f"재료{i}", "category": "채소",
        "bit_id": i, "default_shelf_days": 10, "risk_factor": 1.0,
    }
    for i in range(25)
]


def test_generate_user_returns_user_state():
    rng = random.Random(42)
    state = generate_user(0, _SAMPLE_MASTERS, rng)
    assert isinstance(state, UserState)


def test_generate_user_inventory_count_in_range():
    rng = random.Random(42)
    state = generate_user(0, _SAMPLE_MASTERS, rng)
    assert 10 <= len(state.inventory) <= 20


def test_generate_user_items_type():
    rng = random.Random(42)
    state = generate_user(0, _SAMPLE_MASTERS, rng)
    for item in state.inventory:
        assert isinstance(item, VirtualInventoryItem)


def test_generate_user_expire_after_registered():
    rng = random.Random(42)
    state = generate_user(0, _SAMPLE_MASTERS, rng)
    for item in state.inventory:
        assert item.expire_date >= item.registered_date


def test_generate_user_initial_waste_zero():
    rng = random.Random(42)
    state = generate_user(0, _SAMPLE_MASTERS, rng)
    assert state.total_wasted == 0.0
    assert state.wasted_by_day == []
    assert state.wasted_by_category == {}


def test_generate_user_risk_factor_from_master():
    masters = [{"id": 0, "name": "A", "category": "육류", "bit_id": 0,
                "default_shelf_days": 5, "risk_factor": 3.0}]
    rng = random.Random(0)
    state = generate_user(0, masters, rng)
    assert state.inventory[0].risk_factor == 3.0
