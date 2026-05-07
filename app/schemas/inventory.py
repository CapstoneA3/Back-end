from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Literal
from app.schemas.ingredient import IngredientMasterRead


class InventoryCreate(BaseModel):
    ingredient_master_id: int
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit: Optional[str] = None
    expire_date: Optional[date] = None


class InventoryUpdate(BaseModel):
    quantity: Optional[Decimal] = Field(default=None, ge=0)
    unit: Optional[str] = None
    expire_date: Optional[date] = None


class InventoryRead(BaseModel):
    id: int
    user_id: str
    ingredient_master_id: int
    quantity: Decimal
    unit: Optional[str]
    expire_date: date
    created_at: datetime
    ingredient: IngredientMasterRead
    traffic_light: Literal["red", "yellow", "green"] = "green"
    score: float = 0.0

    model_config = {"from_attributes": True}


class InventoryDashboard(BaseModel):
    items: list[InventoryRead]
    total: int
