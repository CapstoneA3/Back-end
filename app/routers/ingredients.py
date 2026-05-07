from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.core.database import get_db
from app.models.ingredient import IngredientMaster
from app.schemas.ingredient import IngredientMasterRead
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get(
    "",
    response_model=ApiResponse[List[IngredientMasterRead]],
    summary="식재료 목록 조회",
    description=(
        "식재료 마스터 전체 목록을 반환합니다. `q`와 `category`를 조합해 필터링할 수 있습니다.\n\n"
        "**카테고리 목록:** 곡류/면/떡, 육류, 생선/해산물, 채소, 계란/콩/두부, "
        "유제품/치즈, 김치/절임/묵, 해조류/건어물, 과일/견과, 가공식품/기타, 조미료"
    ),
)
async def list_ingredients(
    q: Optional[str] = Query(None, description="식재료명 부분 검색 (대소문자 무시)", examples=["양파"]),
    category: Optional[str] = Query(None, description="카테고리 정확 일치 필터", examples=["채소"]),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(IngredientMaster)
    if q:
        stmt = stmt.where(IngredientMaster.name.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(IngredientMaster.category == category)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return ApiResponse(success=True, data=items)


@router.get(
    "/{ingredient_id}",
    response_model=ApiResponse[IngredientMasterRead],
    summary="식재료 단건 조회",
    description="ID로 식재료 마스터 단건 정보를 조회합니다.",
    responses={
        404: {"description": "존재하지 않는 ingredient_id"},
    },
)
async def get_ingredient(ingredient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IngredientMaster).where(IngredientMaster.id == ingredient_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return ApiResponse(success=True, data=item)
