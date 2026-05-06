from fastapi import Header, HTTPException, Depends
from supabase import AsyncClient
from app.core.supabase_client import get_supabase


async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    supabase: AsyncClient = Depends(get_supabase),
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        response = await supabase.auth.get_user(token)
        if response.user is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return response.user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user_id(user=Depends(get_current_user)) -> str:
    return str(user.id)
