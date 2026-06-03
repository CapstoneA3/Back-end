from __future__ import annotations
from collections import defaultdict

from simulate.data_gen import UserState


def aggregate(
    results_alpha: list[UserState],
    results_random: list[UserState],
) -> dict:
    total_alpha = sum(s.total_wasted for s in results_alpha)
    total_random = sum(s.total_wasted for s in results_random)
    reduction = (
        (total_random - total_alpha) / total_random * 100
        if total_random > 0 else 0.0
    )

    n_users = len(results_alpha)
    n_days = len(results_alpha[0].wasted_by_day) if results_alpha else 0

    daily_alpha = [
        sum(s.wasted_by_day[d] for s in results_alpha) / n_users
        for d in range(n_days)
    ]
    daily_random = [
        sum(s.wasted_by_day[d] for s in results_random) / n_users
        for d in range(n_days)
    ]

    cat_alpha: dict[str, float] = defaultdict(float)
    for s in results_alpha:
        for cat, waste in s.wasted_by_category.items():
            cat_alpha[cat] += waste

    cat_random: dict[str, float] = defaultdict(float)
    for s in results_random:
        for cat, waste in s.wasted_by_category.items():
            cat_random[cat] += waste

    return {
        "total_waste_alpha": total_alpha,
        "total_waste_random": total_random,
        "waste_reduction_rate": reduction,
        "waste_by_day_alpha": daily_alpha,
        "waste_by_day_random": daily_random,
        "waste_by_category_alpha": dict(cat_alpha),
        "waste_by_category_random": dict(cat_random),
    }
