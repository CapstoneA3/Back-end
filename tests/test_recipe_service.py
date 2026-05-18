from app.models.recipe import Recipe, RecipeIngredient, RecipeStep


def test_recipe_model_importable():
    r = Recipe()
    r.id = 1
    r.name = "계란볶음밥"
    r.cook_time_min = 15
    r.servings = 2
    r.recipe_bit = None
    assert r.name == "계란볶음밥"


def test_recipe_ingredient_model_importable():
    ri = RecipeIngredient()
    ri.recipe_id = 1
    ri.ingredient_master_id = 5
    ri.quantity = "2"
    ri.unit = "개"
    ri.ingredient_name = "계란"
    assert ri.ingredient_name == "계란"


def test_recipe_step_model_importable():
    rs = RecipeStep()
    rs.recipe_id = 1
    rs.step_order = 1
    rs.description = "팬을 달군다"
    rs.tip = None
    assert rs.description == "팬을 달군다"


from app.schemas.recipe import (
    RecipeIngredientRead,
    RecipeStepRead,
    RecipeRecommendItem,
    RecipeRecommendList,
    RecipeDetailRead,
)


def test_recipe_ingredient_read_schema():
    obj = RecipeIngredientRead.model_validate({
        "id": 1, "recipe_id": 10, "ingredient_master_id": 5,
        "quantity": "2", "unit": "개", "ingredient_name": "계란",
    })
    assert obj.ingredient_name == "계란"
    assert obj.ingredient_master_id == 5


def test_recipe_step_read_schema():
    obj = RecipeStepRead.model_validate({
        "id": 1, "recipe_id": 10, "step_order": 1,
        "description": "팬을 달군다", "tip": None,
    })
    assert obj.step_order == 1
    assert obj.tip is None


def test_recipe_recommend_item_schema():
    item = RecipeRecommendItem(
        id=1, name="계란볶음밥", cook_time_min=15, servings=2,
        score=42.5, rank=1, ingredients=[],
    )
    assert item.rank == 1
    assert item.score == 42.5


def test_recipe_recommend_list_schema():
    lst = RecipeRecommendList(items=[], total=0)
    assert lst.total == 0


def test_recipe_detail_read_schema():
    detail = RecipeDetailRead(
        id=1, name="계란볶음밥", cook_time_min=15, servings=2,
        ingredients=[], steps=[],
    )
    assert detail.name == "계란볶음밥"


from datetime import date, timedelta
from unittest.mock import MagicMock
from app.services.recipe_service import _calc_score, _filter_by_bitset, _score_recipe


def test_calc_score_normal():
    exp = date.today() + timedelta(days=1)
    score = _calc_score(3.0, 200.0, exp)
    assert score == 3.0 * 200.0 / (1**2 + 1)   # 300.0


def test_calc_score_clips_to_1_when_expired():
    exp = date.today() - timedelta(days=3)
    score = _calc_score(1.0, 100.0, exp)
    assert score == 1.0 * 100.0 / (1**2 + 1)   # 50.0  (days_left clamped to 1)


def test_filter_by_bitset_exact_match():
    user_bitset = (1 << 0) | (1 << 2)
    recipe_mask = (1 << 0) | (1 << 2)
    assert _filter_by_bitset(user_bitset, [recipe_mask]) == [True]


def test_filter_by_bitset_missing_ingredient():
    user_bitset = (1 << 0)
    recipe_mask = (1 << 0) | (1 << 2)
    assert _filter_by_bitset(user_bitset, [recipe_mask]) == [False]


def test_filter_by_bitset_skips_none_mask():
    assert _filter_by_bitset((1 << 0), [None]) == [False]


def test_filter_by_bitset_skips_zero_mask():
    assert _filter_by_bitset((1 << 0), [0]) == [False]


def test_score_recipe_sums_ingredient_scores():
    today = date.today()
    inv_lookup = {
        5:  [(100.0, today + timedelta(days=5), 1.0)],
        10: [(50.0,  today + timedelta(days=2), 2.0)],
    }
    ri_5 = MagicMock()
    ri_5.ingredient_master_id = 5
    ri_10 = MagicMock()
    ri_10.ingredient_master_id = 10

    score = _score_recipe([ri_5, ri_10], inv_lookup)
    expected = 1.0 * 100.0 / (5**2 + 1) + 2.0 * 50.0 / (2**2 + 1)
    assert abs(score - expected) < 1e-9


def test_score_recipe_ignores_missing_inv():
    ri = MagicMock()
    ri.ingredient_master_id = 5
    assert _score_recipe([ri], {}) == 0.0
