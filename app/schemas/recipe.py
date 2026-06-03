from pydantic import BaseModel, Field
from typing import Optional


class RecipeIngredientRead(BaseModel):
    id: int = Field(description="재료 항목 ID")
    recipe_id: int = Field(description="레시피 ID")
    ingredient_master_id: Optional[int] = Field(default=None, description="식재료 마스터 ID")
    quantity: Optional[str] = Field(default=None, description="필요 수량")
    unit: Optional[str] = Field(default=None, description="단위")
    ingredient_name: Optional[str] = Field(default=None, description="식재료명")

    model_config = {"from_attributes": True}


class RecipeStepRead(BaseModel):
    id: int = Field(description="단계 ID")
    recipe_id: int = Field(description="레시피 ID")
    step_order: int = Field(description="조리 순서")
    description: str = Field(description="조리 설명")
    tip: Optional[str] = Field(default=None, description="팁")

    model_config = {"from_attributes": True}


class RecipeRecommendItem(BaseModel):
    id: int = Field(description="레시피 ID")
    name: str = Field(description="레시피명")
    cook_time_min: Optional[int] = Field(default=None, description="조리 시간(분)")
    servings: Optional[int] = Field(default=None, description="인분 수")
    score: float = Field(description="α-스코어 합산 (높을수록 우선 추천)")
    rank: int = Field(description="추천 순위 (1위부터)")
    missing_count: int = Field(default=0, description="부족한 재료 수 (0이면 완전 조리 가능)")
    missing_ingredients: list[str] = Field(default_factory=list, description="부족한 재료명 목록")
    ingredients: list[RecipeIngredientRead] = Field(description="필요 재료 목록")


class RecipeRecommendList(BaseModel):
    items: list[RecipeRecommendItem] = Field(description="추천 레시피 목록 (스코어 내림차순)")
    total: int = Field(description="결과 수")


class RecipeDetailRead(BaseModel):
    id: int = Field(description="레시피 ID")
    name: str = Field(description="레시피명")
    cook_time_min: Optional[int] = Field(default=None, description="조리 시간(분)")
    servings: Optional[int] = Field(default=None, description="인분 수")
    ingredients: list[RecipeIngredientRead] = Field(description="필요 재료 목록")
    steps: list[RecipeStepRead] = Field(description="조리 순서 목록")
