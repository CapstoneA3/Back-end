from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from app.routers import ingredients, inventory, auth

app = FastAPI(
    title="냉장고 재고 관리 API",
    version="0.1.0",
    description="""
개인 냉장고의 식재료를 관리하고 최적 레시피를 추천하는 백엔드 API.

## 인증

보호된 엔드포인트는 **Bearer JWT 토큰**이 필요합니다.

1. `POST /api/v1/auth/signup` 또는 `POST /api/v1/auth/login`으로 토큰 발급
2. 이후 요청 헤더에 포함: `Authorization: Bearer <access_token>`
""",
    openapi_tags=[
        {"name": "auth", "description": "회원가입, 로그인, 내 정보 조회"},
        {"name": "ingredients", "description": "식재료 마스터 데이터 검색 및 단건 조회"},
        {"name": "inventory", "description": "냉장고 재고 등록·조회·수정·삭제 (인증 필요)"},
    ],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(ingredients.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")


@app.get("/health", tags=["health"], summary="헬스 체크", include_in_schema=False)
async def health_check():
    return {"status": "ok"}


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    schema.setdefault("components", {})["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Supabase Auth에서 발급된 JWT 액세스 토큰",
        }
    }
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi
