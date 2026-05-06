from fastapi import APIRouter, Depends
from supabase import AsyncClient
from app.core.supabase_client import get_supabase
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, MeResponse
from app.schemas.common import ApiResponse
from app.services.auth_service import signup, login
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=ApiResponse[TokenResponse], status_code=201)
async def signup_route(
    data: SignupRequest,
    supabase: AsyncClient = Depends(get_supabase),
):
    result = await signup(supabase, data.email, data.password)
    return ApiResponse(success=True, data=result, message="회원가입이 완료되었습니다.")


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login_route(
    data: LoginRequest,
    supabase: AsyncClient = Depends(get_supabase),
):
    result = await login(supabase, data.email, data.password)
    return ApiResponse(success=True, data=result)


@router.get("/me", response_model=ApiResponse[MeResponse])
async def me_route(user=Depends(get_current_user)):
    return ApiResponse(
        success=True,
        data={
            "id": str(user.id),
            "email": user.email,
            "created_at": str(user.created_at),
        },
    )
