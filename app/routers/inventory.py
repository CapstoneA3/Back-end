from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal
from app.core.database import get_db
from app.dependencies.auth import get_current_user_id
from app.schemas.inventory import InventoryCreate, InventoryRead, InventoryDashboard, InventoryUpdate
from app.schemas.common import ApiResponse
from app.services.inventory_service import register_ingredient, get_dashboard, delete_inventory_item, update_inventory_item

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("", response_model=ApiResponse[InventoryRead], status_code=201)
async def add_inventory(
    data: InventoryCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    item = await register_ingredient(db, user_id, data)
    return ApiResponse(success=True, data=item, message="재료가 등록되었습니다.")


@router.get("", response_model=ApiResponse[InventoryDashboard])
async def get_inventory(
    sort: Literal["recommended", "expire_date"] = Query(default="recommended"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    dashboard = await get_dashboard(db, user_id, sort)
    return ApiResponse(success=True, data=dashboard)


@router.patch("/{inventory_id}", response_model=ApiResponse[None], status_code=200)
async def patch_inventory_item(
    inventory_id: int,
    data: InventoryUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await update_inventory_item(db, user_id, inventory_id, data)
    return ApiResponse(success=True, data=None, message="재고가 수정되었습니다.")


@router.delete("/{inventory_id}", response_model=ApiResponse[None], status_code=200)
async def delete_inventory_item_endpoint(
    inventory_id: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await delete_inventory_item(db, user_id, inventory_id)
    return ApiResponse(success=True, data=None, message="재료가 삭제되었습니다.")
