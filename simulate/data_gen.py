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
    recipes: list[dict] | None = None,
) -> UserState:
    """레시피 기반으로 인벤토리 생성.

    recipes가 주어지면 3~5개 레시피의 재료를 먼저 배정해 조리 가능 레시피를 보장한다.
    이후 랜덤 재료를 추가해 총 15~25개를 채운다.
    """
    ing_by_id: dict[int, dict] = {ing["id"]: ing for ing in ingredient_master}
    today = date.today()

    # 레시피 재료 수집 (조리 가능 보장)
    selected_ids: list[int] = []
    if recipes:
        n_recipes = rng.randint(3, 5)
        for recipe in rng.sample(recipes, k=min(n_recipes, len(recipes))):
            for ri in recipe.get("ingredients", []):
                mid = ri.get("ingredient_master_id")
                if mid and mid in ing_by_id and mid not in selected_ids:
                    selected_ids.append(mid)

    # 랜덤 재료로 나머지 채우기 (총 15~25개)
    target = rng.randint(15, 25)
    remaining = [ing["id"] for ing in ingredient_master if ing["id"] not in selected_ids]
    extra_count = max(0, target - len(selected_ids))
    if extra_count > 0 and remaining:
        selected_ids += rng.sample(remaining, k=min(extra_count, len(remaining)))

    selected = [ing_by_id[mid] for mid in selected_ids if mid in ing_by_id]

    # 임박 재료 비율 ~25% 확보
    urgent_count = max(1, round(len(selected) * 0.25))
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
