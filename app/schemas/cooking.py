from pydantic import BaseModel, Field, model_validator


class IngredientUsage(BaseModel):
    ingredient_master_id: int = Field(description="식재료 마스터 ID")
    quantity: float = Field(gt=0, description="실제 사용량 (0 초과)")


class CookRequest(BaseModel):
    ingredients: list[IngredientUsage] = Field(description="사용한 재료 목록")

    @model_validator(mode="after")
    def no_duplicate_ingredients(self) -> "CookRequest":
        seen: set[int] = set()
        for usage in self.ingredients:
            if usage.ingredient_master_id in seen:
                raise ValueError(
                    f"Duplicate ingredient_master_id: {usage.ingredient_master_id}"
                )
            seen.add(usage.ingredient_master_id)
        return self


class InventoryDeduction(BaseModel):
    inventory_id: int = Field(description="차감된 인벤토리 행 ID")
    deducted: float = Field(description="실제 차감된 수량")
    deleted: bool = Field(description="해당 행 삭제 여부 (수량 완전 소진)")


class IngredientDeductionResult(BaseModel):
    ingredient_master_id: int = Field(description="식재료 마스터 ID")
    ingredient_name: str = Field(description="식재료명")
    requested: float = Field(description="요청한 차감 수량")
    deducted: float = Field(description="실제 차감된 총량 (재고 부족 시 < requested)")
    rows_affected: list[InventoryDeduction] = Field(description="영향받은 인벤토리 행 목록")


class CookResult(BaseModel):
    recipe_id: int = Field(description="요리한 레시피 ID")
    recipe_name: str = Field(description="레시피명")
    deductions: list[IngredientDeductionResult] = Field(description="재료별 차감 결과")
