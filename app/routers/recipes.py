from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.dependencies.auth import get_current_user_id
from app.schemas.recipe import RecipeRecommendList, RecipeDetailRead
from app.schemas.common import ApiResponse
from app.services.recipe_service import get_recommended_recipes, get_recipe_detail

router = APIRouter(prefix="/recipes", tags=["recipes"])

_BEARER = {"security": [{"bearerAuth": []}]}
_AUTH_401 = {401: {"description": "Authorization 헤더 없음 또는 토큰 만료·무효"}}


@router.get(
    "",
    response_model=ApiResponse[RecipeRecommendList],
    summary="추천 레시피 목록",
    description=(
        "사용자 냉장고 재료(BitSet)로 만들 수 있는 레시피를 α-스코어 순으로 반환합니다.\n\n"
        "- BitSet AND 연산으로 조리 가능 레시피 필터링\n"
        "- α-스코어: 유통기한 임박·위험도 높은 재료를 소비하는 레시피 우선 순위\n\n"
        "**Bearer 토큰 필수.**"
    ),
    responses=_AUTH_401,
    openapi_extra=_BEARER,
)
async def list_recipes(
    limit: int = Query(default=20, ge=1, le=100, description="반환할 레시피 최대 수"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    result = await get_recommended_recipes(db, redis, user_id, limit)
    return ApiResponse(success=True, data=result)


@router.get(
    "/{recipe_id}",
    response_model=ApiResponse[RecipeDetailRead],
    summary="레시피 상세 조회",
    description="레시피 ID로 상세 정보, 필요 재료, 조리 순서를 반환합니다.",
    responses={404: {"description": "존재하지 않는 recipe_id"}},
)
async def get_recipe(
    recipe_id: int,
    db: AsyncSession = Depends(get_db),
):
    recipe = await get_recipe_detail(db, recipe_id)
    return ApiResponse(success=True, data=recipe)
