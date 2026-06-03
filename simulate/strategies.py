from __future__ import annotations
import random
from datetime import date

from simulate.data_gen import UserState
from simulate.engine import build_bitset, _calc_score


def is_cookable(user_bitset: int, recipe_bit: int | None) -> bool:
    if not recipe_bit:
        return False
    return (user_bitset & recipe_bit) == recipe_bit


def pick_alpha_score(
    state: UserState,
    recipes: list[dict],
    sim_date: date,
) -> dict | None:
    user_bitset = build_bitset(state.inventory)
    cookable = [r for r in recipes if is_cookable(user_bitset, r.get("recipe_bit"))]
    if not cookable:
        return None

    inv_by_id: dict[int, list] = {}
    for item in state.inventory:
        inv_by_id.setdefault(item.ingredient_master_id, []).append(item)

    def score(recipe: dict) -> float:
        total = 0.0
        for ri in recipe.get("ingredients", []):
            mid = ri.get("ingredient_master_id")
            if mid is None:
                continue
            for item in inv_by_id.get(mid, []):
                total += _calc_score(item.risk_factor, item.quantity, item.expire_date, sim_date)
        return total

    return max(cookable, key=score)


def pick_random(
    state: UserState,
    recipes: list[dict],
    sim_date: date,
) -> dict | None:
    user_bitset = build_bitset(state.inventory)
    cookable = [r for r in recipes if is_cookable(user_bitset, r.get("recipe_bit"))]
    return random.choice(cookable) if cookable else None
