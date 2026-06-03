from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
import random as _random_module


@dataclass
class VirtualInventoryItem:
    ingredient_master_id: int
    name: str
    category: str
    bit_id: int
    risk_factor: float
    quantity: float
    registered_date: date
    expire_date: date


@dataclass
class UserState:
    user_id: int
    inventory: list[VirtualInventoryItem] = field(default_factory=list)
    total_wasted: float = 0.0
    wasted_by_day: list[float] = field(default_factory=list)
    wasted_by_category: dict[str, float] = field(default_factory=dict)


def generate_user(
    user_id: int,
    ingredient_master: list[dict],
    rng: _random_module.Random,
) -> UserState:
    n = len(ingredient_master)
    lo = min(10, n)
    hi = min(20, n)
    k = rng.randint(lo, hi)
    selected = rng.sample(ingredient_master, k=k)
    today = date.today()

    # 임박 재료 비율 ~25% 확보
    urgent_count = max(1, round(k * 0.25))
    items: list[VirtualInventoryItem] = []

    for idx, ing in enumerate(selected):
        shelf = ing["default_shelf_days"] or 7
        if idx < urgent_count:
            expire = today + timedelta(days=rng.randint(1, 3))
        else:
            offset = rng.randint(0, shelf // 2)
            expire = today - timedelta(days=offset) + timedelta(
                days=shelf + rng.randint(-2, 2)
            )
        registered = min(today, expire - timedelta(days=1))

        items.append(VirtualInventoryItem(
            ingredient_master_id=ing["id"],
            name=ing["name"],
            category=ing["category"],
            bit_id=ing["bit_id"],
            risk_factor=float(ing["risk_factor"]),
            quantity=rng.uniform(50, 500),
            registered_date=registered,
            expire_date=expire,
        ))

    return UserState(user_id=user_id, inventory=items)
