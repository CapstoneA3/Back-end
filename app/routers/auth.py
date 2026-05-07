from fastapi import APIRouter, Depends
from supabase import AsyncClient
from app.core.supabase_client import get_supabase
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, MeResponse
from app.schemas.common import ApiResponse
from app.services.auth_service import signup, login
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

_AUTH_401 = {401: {"description": "Authorization 헤더 없음 또는 토큰 만료·무효"}}


@router.post(
    "/signup",
    response_model=ApiResponse[TokenResponse],
    status_code=201,
    summary="회원가입",
    description=(
        "이메일·비밀번호로 신규 계정을 생성하고 JWT 액세스 토큰을 반환합니다.\n\n"
        "- 이미 등록된 이메일이면 `400` 반환\n"
        "- Supabase 프로젝트 설정에서 이메일 확인이 활성화된 경우 세션 없이 `400` 반환"
    ),
    responses={
        400: {"description": "이미 등록된 이메일 또는 잘못된 입력값"},
    },
)
async def signup_route(
    data: SignupRequest,
    supabase: AsyncClient = Depends(get_supabase),
):
    result = await signup(supabase, data.email, data.password)
    return ApiResponse(success=True, data=result, message="회원가입이 완료되었습니다.")


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    summary="로그인",
    description="이메일·비밀번호로 로그인하고 JWT 액세스 토큰을 반환합니다.",
    responses={
        401: {"description": "이메일 또는 비밀번호 불일치"},
    },
)
async def login_route(
    data: LoginRequest,
    supabase: AsyncClient = Depends(get_supabase),
):
    result = await login(supabase, data.email, data.password)
    return ApiResponse(success=True, data=result)


@router.get(
    "/me",
    response_model=ApiResponse[MeResponse],
    summary="내 정보 조회",
    description="현재 로그인된 사용자의 계정 정보를 반환합니다. **Bearer 토큰 필수.**",
    responses=_AUTH_401,
    openapi_extra={"security": [{"bearerAuth": []}]},
)
async def me_route(user=Depends(get_current_user)):
    return ApiResponse(
        success=True,
        data={
            "id": str(user.id),
            "email": user.email,
            "created_at": str(user.created_at),
        },
    )
