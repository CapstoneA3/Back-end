import random
from datetime import date, timedelta

from simulate.data_gen import UserState, VirtualInventoryItem
from simulate.strategies import is_cookable, pick_alpha_score, pick_random


def _item(mid: int, bit_id: int, days: int = 5, qty: float = 100.0, rf: float = 1.0) -> VirtualInventoryItem:
    today = date.today()
    return VirtualInventoryItem(
        ingredient_master_id=mid, name=f"재료{mid}", category="채소",
        bit_id=bit_id, risk_factor=rf, quantity=qty,
        registered_date=today, expire_date=today + timedelta(days=days),
    )


def _state(*items: VirtualInventoryItem) -> UserState:
    return UserState(user_id=1, inventory=list(items))


# ── is_cookable ────────────────────────────────────────────────────────────────

def test_is_cookable_exact_match():
    bitset = (1 << 0) | (1 << 1)
    assert is_cookable(bitset, (1 << 0) | (1 << 1)) is True


def test_is_cookable_superset():
    bitset = (1 << 0) | (1 << 1) | (1 << 2)
    assert is_cookable(bitset, (1 << 0) | (1 << 1)) is True


def test_is_cookable_partial_match_above_threshold():
    # 4/5 = 80% → True (기본 임계값 0.8)
    bitset = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3)
    assert is_cookable(bitset, (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4)) is True


def test_is_cookable_partial_match_below_threshold():
    # 1/2 = 50% → False
    bitset = (1 << 0)
    assert is_cookable(bitset, (1 << 0) | (1 << 1)) is False


def test_is_cookable_none_recipe_bit():
    assert is_cookable(0b111, None) is False


def test_is_cookable_zero_recipe_bit():
    assert is_cookable(0b111, 0) is False


# ── pick_alpha_score ───────────────────────────────────────────────────────────

def test_pick_alpha_score_returns_none_when_no_cookable():
    state = _state(_item(mid=0, bit_id=0))
    recipes = [{"name": "없는레시피", "recipe_bit": (1 << 9), "ingredients": []}]
    assert pick_alpha_score(state, recipes, date.today()) is None


def test_pick_alpha_score_prefers_urgent_recipe():
    today = date.today()
    # 재료 0: 임박(1일), risk=3  → 레시피A 선택 기대
    # 재료 1: 여유(10일), risk=1 → 레시피B
    state = UserState(user_id=1, inventory=[
        _item(mid=0, bit_id=0, days=1, rf=3.0),
        _item(mid=1, bit_id=1, days=10, rf=1.0),
    ])
    recipe_a = {
        "name": "레시피A", "recipe_bit": (1 << 0),
        "ingredients": [{"ingredient_master_id": 0, "quantity": "100"}],
    }
    recipe_b = {
        "name": "레시피B", "recipe_bit": (1 << 1),
        "ingredients": [{"ingredient_master_id": 1, "quantity": "100"}],
    }
    result = pick_alpha_score(state, [recipe_a, recipe_b], today)
    assert result["name"] == "레시피A"


def test_pick_alpha_score_returns_single_cookable():
    state = _state(_item(mid=0, bit_id=0))
    recipes = [
        {"name": "조리가능", "recipe_bit": (1 << 0), "ingredients": []},
        {"name": "조리불가", "recipe_bit": (1 << 9), "ingredients": []},
    ]
    result = pick_alpha_score(state, recipes, date.today())
    assert result["name"] == "조리가능"


# ── pick_random ────────────────────────────────────────────────────────────────

def test_pick_random_returns_none_when_no_cookable():
    state = _state(_item(mid=0, bit_id=0))
    recipes = [{"name": "없는레시피", "recipe_bit": (1 << 9), "ingredients": []}]
    assert pick_random(state, recipes, date.today()) is None


def test_pick_random_returns_a_cookable_recipe():
    random.seed(0)
    state = _state(_item(mid=0, bit_id=0), _item(mid=1, bit_id=1))
    recipes = [
        {"name": "레시피A", "recipe_bit": (1 << 0), "ingredients": []},
        {"name": "레시피B", "recipe_bit": (1 << 1), "ingredients": []},
    ]
    result = pick_random(state, recipes, date.today())
    assert result is not None
    assert result["name"] in ("레시피A", "레시피B")
