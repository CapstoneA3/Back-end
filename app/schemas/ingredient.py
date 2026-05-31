from pydantic import BaseModel
from decimal import Decimal
from typing import Optional, List


class IngredientMasterRead(BaseModel):
    id: int
    bit_id: int
    name: str
    category: str
    default_shelf_days: Optional[int] = None
    risk_factor: Decimal
    allowed_units: List[str] = []

    model_config = {"from_attributes": True}
