from __future__ import annotations
import re
from datetime import date, timedelta
from typing import Callable

from simulate.data_gen import UserState, VirtualInventoryItem

_QTY_RE = re.compile(r"[\d.]+")


def build_bitset(inventory: list[VirtualInventoryItem]) -> int:
    mask = 0
    for item in inventory:
        mask |= (1 << item.bit_id)
    return mask


def parse_quantity(s: str | None) -> float:
    if not s:
        return 100.0
    m = _QTY_RE.search(s)
    return float(m.group()) if m else 100.0


def _calc_score(risk_factor: float, quantity: float, expire_date: date, sim_date: date) -> float:
    days_left = max(1, (expire_date - sim_date).days)
    return risk_factor * quantity / (days_left ** 2 + 1)


def expire_check(state: UserState, sim_date: date) -> None:
    wasted = 0.0
    remaining: list[VirtualInventoryItem] = []
    for item in state.inventory:
        if item.expire_date < sim_date:
            wasted += item.quantity
            state.wasted_by_category[item.category] = (
                state.wasted_by_category.get(item.category, 0.0) + item.quantity
            )
        else:
            remaining.append(item)
    state.inventory = remaining
    state.wasted_by_day.append(wasted)
    state.total_wasted += wasted


def fifo_deduct(state: UserState, recipe: dict, sim_date: date) -> None:
    for ri in recipe.get("ingredients", []):
        mid = ri.get("ingredient_master_id")
        if mid is None:
            continue
        needed = parse_quantity(ri.get("quantity"))
        batch = sorted(
            [item for item in state.inventory if item.ingredient_master_id == mid],
            key=lambda x: x.expire_date,
        )
        for item in batch:
            if needed <= 0:
                break
            deduct = min(item.quantity, needed)
            item.quantity -= deduct
            needed -= deduct
        state.inventory = [item for item in state.inventory if item.quantity > 0]


def replenish(
    state: UserState,
    sim_day: int,
    ingredient_master: list[dict],
    rng,
) -> None:
    if sim_day == 0 or sim_day % 7 != 0:
        return
    today = date.today()
    k = rng.randint(1, min(3, len(ingredient_master)))
    for ing in rng.sample(ingredient_master, k=k):
        shelf = ing["default_shelf_days"] or 7
        state.inventory.append(VirtualInventoryItem(
            ingredient_master_id=ing["id"],
            name=ing["name"],
            category=ing["category"],
            bit_id=ing["bit_id"],
            risk_factor=float(ing["risk_factor"]),
            quantity=rng.uniform(50, 300),
            registered_date=today,
            expire_date=today + timedelta(days=shelf),
        ))


def step(
    state: UserState,
    recipes: list[dict],
    sim_date: date,
    sim_day: int,
    ingredient_master: list[dict],
    strategy: Callable,
    rng,
) -> None:
    expire_check(state, sim_date)
    recipe = strategy(state, recipes, sim_date)
    if recipe:
        fifo_deduct(state, recipe, sim_date)
    replenish(state, sim_day, ingredient_master, rng)
