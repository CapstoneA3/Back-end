from typing import Optional
from fastapi import Header, HTTPException, Depends
from supabase import AsyncClient
from app.core.supabase_client import get_supabase

_AUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    supabase: AsyncClient = Depends(get_supabase),
):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required", headers=_AUTH_HEADERS)
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required", headers=_AUTH_HEADERS)
    token = authorization.removeprefix("Bearer ").strip()
    try:
        response = await supabase.auth.get_user(token)
        if response.user is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token", headers=_AUTH_HEADERS)
        return response.user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers=_AUTH_HEADERS)


async def get_current_user_id(user=Depends(get_current_user)) -> str:
    return str(user.id)
