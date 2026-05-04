from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.core.database import get_db
from app.models.ingredient import IngredientMaster
from app.schemas.ingredient import IngredientMasterRead
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


@router.get("", response_model=ApiResponse[List[IngredientMasterRead]])
async def list_ingredients(
    q: Optional[str] = Query(None, description="식재료명 검색"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
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


@router.get("/{ingredient_id}", response_model=ApiResponse[IngredientMasterRead])
async def get_ingredient(ingredient_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IngredientMaster).where(IngredientMaster.id == ingredient_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return ApiResponse(success=True, data=item)
