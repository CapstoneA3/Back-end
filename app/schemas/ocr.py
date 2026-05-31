from decimal import Decimal
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.inventory import InventoryRead


class OcrRawItem(BaseModel):
    text: str


class OcrCandidate(BaseModel):
    ingredient_master_id: int = Field(description="ingredient_master 고유 ID")
    ingredient_name: str = Field(description="매칭된 식재료 표준명")
    confidence: float = Field(ge=0, le=100, description="매칭 신뢰도 (0~100)")


class OcrScanCandidate(BaseModel):
    raw_text: str = Field(description="OCR이 인식한 영수증 원문 텍스트")
    recommended_action: Literal["register", "review", "skip"] = Field(
        description=(
            "프론트 권장 처리 방법. "
            "`register`: 신뢰도 90% 이상, 자동 선택 후 confirm 권장. "
            "`review`: 신뢰도 60~89%, 사용자가 candidates 또는 검색으로 직접 선택 필요. "
            "`skip`: 신뢰도 60% 미만 또는 비식재료 항목(부가세·봉투 등), 등록 불필요."
        )
    )
    candidates: list[OcrCandidate] = Field(
        description=(
            "매칭 후보 목록 (최대 3개, 신뢰도 내림차순). "
            "`skip`인 경우 비식재료 키워드로 제외된 항목은 빈 배열."
        )
    )


class OcrScanResult(BaseModel):
    items: list[OcrScanCandidate] = Field(description="영수증에서 인식된 품목별 매칭 결과 목록")


class OcrConfirmItem(BaseModel):
    ingredient_master_id: int = Field(
        description=(
            "등록할 식재료의 ingredient_master ID. "
            "scan 결과의 candidates에서 선택하거나, "
            "/api/v1/ingredients?search= 검색으로 직접 지정."
        )
    )
    quantity: Decimal = Field(gt=0, description="등록 수량 (소수점 가능, 0 초과)")
    expire_date: date | None = Field(
        default=None,
        description="유통기한 (YYYY-MM-DD). 생략 시 ingredient_master의 default_shelf_days 기준 자동 계산."
    )


class OcrConfirmRequest(BaseModel):
    items: list[OcrConfirmItem] = Field(description="확정 등록할 품목 목록")


class OcrConfirmError(BaseModel):
    ingredient_master_id: int = Field(description="등록 실패한 식재료 ID")
    reason: str = Field(description="실패 사유")


class OcrConfirmResult(BaseModel):
    registered: list[InventoryRead] = Field(default=[], description="등록 성공한 인벤토리 항목 목록")
    errors: list[OcrConfirmError] = Field(default=[], description="등록 실패한 항목 목록")
