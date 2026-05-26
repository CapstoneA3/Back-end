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
        "- `recommended_action: register` — 매칭 신뢰도 70% 이상, 등록 권장\n"
        "- `recommended_action: skip` — 매칭 실패 또는 비식재료 품목\n\n"
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
        "- `expire_date` 생략 시 `default_shelf_days` 기준 자동 계산\n"
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
