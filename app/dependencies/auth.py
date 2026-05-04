from fastapi import Header, HTTPException


async def get_current_user_id(x_user_id: str = Header(..., alias="X-User-ID")) -> str:
    """임시 인증: X-User-ID 헤더에서 user_id 추출. 실제 인증 구현 시 이 함수만 교체."""
    if not x_user_id.strip():
        raise HTTPException(status_code=401, detail="X-User-ID header is required")
    return x_user_id.strip()
