import pytest
from unittest.mock import patch, AsyncMock
from app.schemas.recipe import (
    RecipeRecommendList, RecipeRecommendItem,
    RecipeDetailRead, RecipeIngredientRead, RecipeStepRead,
)


def _make_recommend_list(n: int = 1) -> RecipeRecommendList:
    items = [
        RecipeRecommendItem(
            id=i + 1, name=f"레시피{i + 1}",
            cook_time_min=20, servings=2,
            score=float(100 - i), rank=i + 1, ingredients=[],
        )
        for i in range(n)
    ]
    return RecipeRecommendList(items=items, total=n)


def _make_detail() -> RecipeDetailRead:
    return RecipeDetailRead(
        id=1, name="계란볶음밥", cook_time_min=15, servings=2,
        ingredients=[
            RecipeIngredientRead(
                id=10, recipe_id=1, ingredient_master_id=5,
                quantity="2", unit="개", ingredient_name="계란",
            )
        ],
        steps=[
            RecipeStepRead(
                id=20, recipe_id=1, step_order=1,
                description="팬을 달군다", tip=None,
            )
        ],
    )


@pytest.mark.asyncio
async def test_get_recipes_returns_200(real_client):
    recommend = _make_recommend_list(2)
    with patch("app.routers.recipes.get_recommended_recipes", AsyncMock(return_value=recommend)):
        resp = await real_client.get("/api/v1/recipes")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total"] == 2
    assert body["data"]["items"][0]["rank"] == 1


@pytest.mark.asyncio
async def test_get_recipes_with_limit(real_client):
    recommend = _make_recommend_list(1)
    with patch("app.routers.recipes.get_recommended_recipes", AsyncMock(return_value=recommend)):
        resp = await real_client.get("/api/v1/recipes?limit=5")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_recipe_detail_returns_200(real_client):
    detail = _make_detail()
    with patch("app.routers.recipes.get_recipe_detail", AsyncMock(return_value=detail)):
        resp = await real_client.get("/api/v1/recipes/1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["name"] == "계란볶음밥"
    assert len(body["data"]["ingredients"]) == 1
    assert len(body["data"]["steps"]) == 1


@pytest.mark.asyncio
async def test_get_recipe_detail_not_found(real_client):
    from fastapi import HTTPException
    with patch(
        "app.routers.recipes.get_recipe_detail",
        AsyncMock(side_effect=HTTPException(status_code=404, detail="Recipe not found")),
    ):
        resp = await real_client.get("/api/v1/recipes/9999")

    assert resp.status_code == 404
