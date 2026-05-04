from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.dependencies.auth import get_current_user_id
from app.schemas.inventory import InventoryCreate, InventoryRead
from app.schemas.common import ApiResponse
from app.services.inventory_service import register_ingredient

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
