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
