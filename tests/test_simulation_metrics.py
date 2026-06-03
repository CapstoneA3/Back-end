from simulate.data_gen import UserState
from simulate.metrics import aggregate


def _states(n: int, total: float, daily: list[float], by_cat: dict) -> list[UserState]:
    return [
        UserState(
            user_id=i,
            total_wasted=total,
            wasted_by_day=daily.copy(),
            wasted_by_category=by_cat.copy(),
        )
        for i in range(n)
    ]


def test_aggregate_waste_reduction_50pct():
    alpha = _states(1, 100.0, [100.0], {})
    rand = _states(1, 200.0, [200.0], {})
    m = aggregate(alpha, rand)
    assert abs(m["waste_reduction_rate"] - 50.0) < 1e-9


def test_aggregate_totals():
    alpha = _states(2, 50.0, [50.0], {})
    rand = _states(2, 100.0, [100.0], {})
    m = aggregate(alpha, rand)
    assert m["total_waste_alpha"] == 100.0
    assert m["total_waste_random"] == 200.0


def test_aggregate_daily_average():
    alpha = _states(2, 0.0, [10.0, 20.0], {})
    rand = _states(2, 0.0, [20.0, 40.0], {})
    m = aggregate(alpha, rand)
    assert m["waste_by_day_alpha"] == [10.0, 20.0]
    assert m["waste_by_day_random"] == [20.0, 40.0]


def test_aggregate_category_sums():
    alpha = _states(1, 0.0, [], {"채소": 60.0, "육류": 40.0})
    rand = _states(1, 0.0, [], {"채소": 120.0, "육류": 80.0})
    m = aggregate(alpha, rand)
    assert m["waste_by_category_alpha"]["채소"] == 60.0
    assert m["waste_by_category_random"]["육류"] == 80.0


def test_aggregate_zero_random_waste_no_div_zero():
    alpha = _states(1, 0.0, [0.0], {})
    rand = _states(1, 0.0, [0.0], {})
    m = aggregate(alpha, rand)
    assert m["waste_reduction_rate"] == 0.0
