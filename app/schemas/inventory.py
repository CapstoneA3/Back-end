from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Literal
from app.schemas.ingredient import IngredientMasterRead


class InventoryCreate(BaseModel):
    ingredient_master_id: int = Field(description="등록할 식재료의 마스터 ID (`ingredient_master.id`)")
    quantity: Decimal = Field(
        default=Decimal("1"),
        gt=0,
        description="보유 수량 (0 초과)",
        examples=["2"],
    )
    unit: Optional[str] = Field(
        default=None,
        description="단위. 생략 시 '개' 기본값 적용",
        examples=["개", "g", "ml"],
    )
    expire_date: Optional[date] = Field(
        default=None,
        description="유통기한 (YYYY-MM-DD). 생략 시 `default_shelf_days` 기준 자동 계산",
        examples=["2026-05-20"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "ingredient_master_id": 42,
                "quantity": "2",
                "unit": "개",
                "expire_date": "2026-05-20",
            }
        }
    }


class InventoryUpdate(BaseModel):
    quantity: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="변경할 수량. **0을 전달하면 해당 항목이 삭제됩니다.**",
        examples=["3"],
    )
    unit: Optional[str] = Field(
        default=None,
        description="변경할 단위",
        examples=["g"],
    )
    expire_date: Optional[date] = Field(
        default=None,
        description="변경할 유통기한 (YYYY-MM-DD)",
        examples=["2026-06-01"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {"quantity": "3", "unit": "g", "expire_date": "2026-06-01"}
        }
    }


class InventoryRead(BaseModel):
    id: int = Field(description="재고 항목 ID")
    user_id: str = Field(description="소유 사용자 UUID")
    ingredient_master_id: int = Field(description="식재료 마스터 ID")
    quantity: Decimal = Field(description="현재 수량")
    unit: Optional[str] = Field(description="단위")
    expire_date: date = Field(description="유통기한")
    created_at: datetime = Field(description="등록 일시")
    ingredient: IngredientMasterRead = Field(description="연결된 식재료 마스터 정보")
    traffic_light: Literal["red", "yellow", "green"] = Field(
        default="green",
        description="유통기한 신호등 (red: 임박/위험, yellow: 주의, green: 여유)",
    )
    score: float = Field(
        default=0.0,
        description="소진 권장 점수. 높을수록 우선 소진 권장 (α × 수량 / (남은일² + 1))",
    )

    model_config = {"from_attributes": True}


class InventoryDashboard(BaseModel):
    items: list[InventoryRead] = Field(description="재고 목록 (정렬 적용)")
    total: int = Field(description="전체 재고 항목 수")
