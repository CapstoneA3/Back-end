from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal
from app.core.database import get_db
from app.dependencies.auth import get_current_user_id
from app.schemas.inventory import InventoryCreate, InventoryRead, InventoryDashboard, InventoryUpdate
from app.schemas.common import ApiResponse
from app.services.inventory_service import register_ingredient, get_dashboard, delete_inventory_item, update_inventory_item

router = APIRouter(prefix="/inventory", tags=["inventory"])

_BEARER = {"security": [{"bearerAuth": []}]}
_AUTH_401 = {401: {"description": "Authorization 헤더 없음 또는 토큰 만료·무효"}}
_ITEM_ERRORS = {
    401: {"description": "Authorization 헤더 없음 또는 토큰 만료·무효"},
    403: {"description": "다른 사용자 소유의 재고 항목"},
    404: {"description": "존재하지 않는 inventory_id"},
}


@router.post(
    "",
    response_model=ApiResponse[InventoryRead],
    status_code=201,
    summary="재고 등록",
    description=(
        "냉장고에 식재료를 등록합니다.\n\n"
        "- `expire_date` 생략 시 `ingredient_master.default_shelf_days` 기준으로 자동 계산\n"
        "- `unit` 생략 시 기본값 '개' 적용\n\n"
        "**Bearer 토큰 필수.**"
    ),
    responses={
        **_AUTH_401,
        404: {"description": "존재하지 않는 ingredient_master_id"},
    },
    openapi_extra=_BEARER,
)
async def add_inventory(
    data: InventoryCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    item = await register_ingredient(db, user_id, data)
    return ApiResponse(success=True, data=item, message="재료가 등록되었습니다.")


@router.get(
    "",
    response_model=ApiResponse[InventoryDashboard],
    summary="재고 대시보드 조회",
    description=(
        "현재 사용자의 냉장고 재고 전체를 조회합니다.\n\n"
        "- `sort=recommended` (기본): α-점수 내림차순 (유통기한 임박 + 위험도 높은 순)\n"
        "- `sort=expire_date`: 유통기한 오름차순\n\n"
        "각 항목에 `traffic_light`(신호등)과 `score`(소진 권장 점수)가 포함됩니다.\n\n"
        "**Bearer 토큰 필수.**"
    ),
    responses=_AUTH_401,
    openapi_extra=_BEARER,
)
async def get_inventory(
    sort: Literal["recommended", "expire_date"] = Query(
        default="recommended",
        description="정렬 기준: `recommended` = α-점수순, `expire_date` = 유통기한순",
    ),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    dashboard = await get_dashboard(db, user_id, sort)
    return ApiResponse(success=True, data=dashboard)


@router.patch(
    "/{inventory_id}",
    response_model=ApiResponse[None],
    status_code=200,
    summary="재고 수정",
    description=(
        "재고 항목의 수량·단위·유통기한을 부분 수정합니다.\n\n"
        "- 전달한 필드만 업데이트 (나머지 유지)\n"
        "- **`quantity=0` 전달 시 해당 항목이 삭제됩니다.**\n\n"
        "**Bearer 토큰 필수.**"
    ),
    responses=_ITEM_ERRORS,
    openapi_extra=_BEARER,
)
async def patch_inventory_item(
    inventory_id: int,
    data: InventoryUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await update_inventory_item(db, user_id, inventory_id, data)
    return ApiResponse(success=True, data=None, message="재고가 수정되었습니다.")


@router.delete(
    "/{inventory_id}",
    response_model=ApiResponse[None],
    status_code=200,
    summary="재고 삭제",
    description="재고 항목을 삭제합니다. **Bearer 토큰 필수.**",
    responses=_ITEM_ERRORS,
    openapi_extra=_BEARER,
)
async def delete_inventory_item_endpoint(
    inventory_id: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await delete_inventory_item(db, user_id, inventory_id)
    return ApiResponse(success=True, data=None, message="재료가 삭제되었습니다.")
