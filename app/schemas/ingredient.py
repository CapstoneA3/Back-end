from pydantic import BaseModel
from decimal import Decimal


class IngredientMasterRead(BaseModel):
    id: int
    bit_id: int
    name: str
    category: str
    default_shelf_days: int
    risk_factor: Decimal

    model_config = {"from_attributes": True}
