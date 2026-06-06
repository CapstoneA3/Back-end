from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
import httpx

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.dependencies.auth import get_current_user_id
from app.schemas.ocr import OcrScanResult, OcrConfirmRequest, OcrConfirmResult, OcrConfirmError
from app.schemas.inventory import InventoryCreate
from app.schemas.common import ApiResponse
from app.services.ocr_service import scan_receipt
from app.services.matching_service import match_items
from app.services.inventory_service import register_ingredient

router = APIRouter(prefix="/ocr", tags=["ocr"])
_BEARER = {"security": [{"bearerAuth": []}]}
_AUTH_401 = {401: {"description": "Authorization 헤더 없음 또는 토큰 만료·무효"}}

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "application/pdf"})


@router.post(
    "/scan",
    response_model=ApiResponse[OcrScanResult],
    summary="영수증 OCR 스캔",
    description=(
        "영수증 이미지를 OCR로 분석하여 식재료 후보 목록을 반환합니다.\n\n"
        "브랜드명·원산지·용량 등 비식재료 텍스트를 전처리로 제거한 뒤 "
        "ingredient_master와 퍼지 매칭하여 신뢰도에 따라 액션을 분류합니다.\n\n"
        "| `recommended_action` | 기준 | 프론트 처리 |\n"
        "|---|---|---|\n"
        "| `register` | 신뢰도 90% 이상 또는 정확 일치 | 자동 선택, 수량 입력 후 confirm |\n"
        "| `review` | 신뢰도 60~89% | raw_text를 보여주고 사용자가 검색·선택 후 confirm |\n"
        "| `skip` | 신뢰도 60% 미만 또는 비식재료(부가세·카드 등) | 목록에서 제외 |\n\n"
        "각 후보 항목(`candidates`)에는 `default_shelf_days`가 포함되어 있어, "
        "confirm 화면에서 예상 유통기한(`오늘 + default_shelf_days`)을 미리 표시하거나 "
        "기본값으로 채울 수 있습니다. `/ocr/confirm`에서 `expire_date`를 생략하면 "
        "이 값으로 자동 계산됩니다.\n\n"
        "`review` 항목은 `/api/v1/ingredients?search=` 로 올바른 식재료를 검색하여 "
        "`ingredient_master_id`를 직접 지정한 뒤 `/ocr/confirm`에 전달합니다.\n\n"
        "**Bearer 토큰 필수.**"
    ),
    responses={
        **_AUTH_401,
        400: {"description": "지원하지 않는 이미지 포맷"},
        413: {"description": "이미지 파일이 너무 큽니다 (최대 10 MB)"},
        503: {"description": "OCR 서비스 미설정"},
        504: {"description": "CLOVA OCR API timeout"},
    },
    openapi_extra=_BEARER,
)
async def scan_receipt_endpoint(
    image: UploadFile = File(..., description="영수증 이미지 (jpeg/png/pdf)"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    image_bytes = await image.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="이미지 파일이 너무 큽니다 (최대 10 MB)")
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="지원하지 않는 이미지 형식")
    try:
        raw_items = await scan_receipt(image_bytes, image.filename or "receipt.jpg")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="OCR service timeout")
    except httpx.UnsupportedProtocol:
        raise HTTPException(status_code=503, detail="OCR 서비스가 설정되지 않았습니다.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (400, 415):
            raise HTTPException(status_code=400, detail="지원하지 않는 이미지 형식")
        raise

    candidates = await match_items(db, raw_items)
    return ApiResponse(success=True, data=OcrScanResult(items=candidates))


@router.post(
    "/confirm",
    response_model=ApiResponse[OcrConfirmResult],
    status_code=201,
    summary="OCR 스캔 결과 확정 등록",
    description=(
        "사용자가 확정한 품목을 인벤토리에 일괄 등록합니다.\n\n"
        "`/ocr/scan` 결과에서 `register` 항목은 자동 선택, `review` 항목은 사용자가 "
        "검색을 통해 올바른 `ingredient_master_id`로 교체한 뒤 이 엔드포인트에 전달합니다.\n\n"
        "- `ingredient_master_id` — scan 결과의 candidates 중 선택하거나 검색으로 직접 지정\n"
        "- `expire_date` 생략 시 ingredient_master의 `default_shelf_days` 기준 자동 계산\n"
        "- 일부 항목 실패 시 성공 항목만 등록되고, 실패 항목은 `errors`에 포함됩니다.\n\n"
        "**Bearer 토큰 필수.**"
    ),
    responses={**_AUTH_401},
    openapi_extra=_BEARER,
)
async def confirm_receipt_endpoint(
    data: OcrConfirmRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    registered = []
    errors: list[OcrConfirmError] = []
    for item in data.items:
        try:
            inv_create = InventoryCreate(
                ingredient_master_id=item.ingredient_master_id,
                quantity=item.quantity,
                unit=item.unit,
                expire_date=item.expire_date,
            )
            result = await register_ingredient(db, redis, user_id, inv_create)
            registered.append(result)
        except HTTPException as e:
            errors.append(OcrConfirmError(
                ingredient_master_id=item.ingredient_master_id,
                reason=e.detail,
            ))
        except Exception:
            errors.append(OcrConfirmError(
                ingredient_master_id=item.ingredient_master_id,
                reason="처리 중 오류가 발생했습니다.",
            ))

    return ApiResponse(
        success=True,
        data=OcrConfirmResult(registered=registered, errors=errors),
        message="재고가 등록되었습니다.",
    )
