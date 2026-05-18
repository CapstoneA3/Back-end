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
