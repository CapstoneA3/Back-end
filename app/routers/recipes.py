from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.dependencies.auth import get_current_user_id
from app.schemas.recipe import RecipeRecommendList, RecipeDetailRead
from app.schemas.common import ApiResponse
from app.schemas.cooking import CookRequest, CookResult
from app.services.recipe_service import get_recommended_recipes, get_recipe_detail
from app.services.cooking_service import cook_recipe

router = APIRouter(prefix="/recipes", tags=["recipes"])

_BEARER = {"security": [{"bearerAuth": []}]}
_AUTH_401 = {401: {"description": "Authorization 헤더 없음 또는 토큰 만료·무효"}}


@router.get(
    "",
    response_model=ApiResponse[RecipeRecommendList],
    summary="추천 레시피 목록",
    description=(
        "사용자 냉장고 재료(BitSet)로 만들 수 있는 레시피를 α-스코어 순으로 반환합니다.\n\n"
        "- `min_match_rate`로 재료 보유 비율 임계값 조절 (기본 0.8 = 80% 이상 보유 시 추천)\n"
        "- α-스코어: 유통기한 임박·위험도 높은 재료를 소비하는 레시피 우선 순위\n"
        "- `missing_count`/`missing_ingredients`: 부족한 재료 수·목록 반환\n\n"
        "**Bearer 토큰 필수.**"
    ),
    responses=_AUTH_401,
    openapi_extra=_BEARER,
)
async def list_recipes(
    limit: int = Query(default=20, ge=1, le=100, description="반환할 레시피 최대 수"),
    min_match_rate: float = Query(
        default=0.8, ge=0.0, le=1.0,
        description="최소 재료 보유 비율 (0.0~1.0). 기본값 0.8 = 재료의 80% 이상 보유 시 추천",
    ),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    result = await get_recommended_recipes(db, redis, user_id, limit, min_match_rate)
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


@router.post(
    "/{recipe_id}/complete",
    response_model=ApiResponse[CookResult],
    status_code=200,
    summary="요리 완료 처리",
    description=(
        "레시피를 채택하여 요리를 완료합니다.\n\n"
        "- `ingredients`에 포함된 재료만 차감 (레시피에 있어도 목록 미포함 시 차감 안 함)\n"
        "- α-스코어 내림차순으로 재고 우선 차감 (유통기한 임박·수량 많은 항목 먼저)\n"
        "- 재고 부족 시 보유량만큼 부분 차감 (`deducted < requested`)\n"
        "- 재고 완전 소진 시 Redis BitSet 해당 비트 자동 클리어\n\n"
        "**Bearer 토큰 필수.**"
    ),
    responses={
        **_AUTH_401,
        404: {"description": "존재하지 않는 recipe_id"},
    },
    openapi_extra=_BEARER,
)
async def cook_recipe_endpoint(
    recipe_id: int,
    data: CookRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    result = await cook_recipe(db, redis, user_id, recipe_id, data)
    return ApiResponse(success=True, data=result, message="요리가 완료되었습니다.")
