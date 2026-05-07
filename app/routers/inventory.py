from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal
import redis.asyncio as aioredis
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.dependencies.auth import get_current_user_id
from app.schemas.inventory import InventoryCreate, InventoryRead, InventoryDashboard
from app.schemas.common import ApiResponse
from app.services.inventory_service import register_ingredient, get_dashboard, delete_inventory_item

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("", response_model=ApiResponse[InventoryRead], status_code=201)
async def add_inventory(
    data: InventoryCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    item = await register_ingredient(db, redis, user_id, data)
    return ApiResponse(success=True, data=item, message="재료가 등록되었습니다.")


@router.get("", response_model=ApiResponse[InventoryDashboard])
async def get_inventory(
    sort: Literal["recommended", "expire_date"] = Query(default="recommended"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    dashboard = await get_dashboard(db, user_id, sort)
    return ApiResponse(success=True, data=dashboard)


@router.delete("/{inventory_id}", response_model=ApiResponse[None], status_code=200)
async def delete_inventory_item_endpoint(
    inventory_id: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    await delete_inventory_item(db, redis, user_id, inventory_id)
    return ApiResponse(success=True, data=None, message="재료가 삭제되었습니다.")
