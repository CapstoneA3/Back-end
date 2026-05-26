from decimal import Decimal
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.inventory import InventoryRead


class OcrRawItem(BaseModel):
    text: str


class OcrCandidate(BaseModel):
    ingredient_master_id: int
    ingredient_name: str
    confidence: float


class OcrScanCandidate(BaseModel):
    raw_text: str
    recommended_action: Literal["register", "skip"]
    candidates: list[OcrCandidate]


class OcrScanResult(BaseModel):
    items: list[OcrScanCandidate]


class OcrConfirmItem(BaseModel):
    ingredient_master_id: int
    quantity: Decimal = Field(gt=0)
    expire_date: date | None = None


class OcrConfirmRequest(BaseModel):
    items: list[OcrConfirmItem]


class OcrConfirmError(BaseModel):
    ingredient_master_id: int
    reason: str


class OcrConfirmResult(BaseModel):
    registered: list[InventoryRead] = []
    errors: list[OcrConfirmError] = []
