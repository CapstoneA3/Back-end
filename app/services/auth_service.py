import logging

from fastapi import HTTPException
from supabase import AsyncClient

logger = logging.getLogger(__name__)


async def signup(supabase: AsyncClient, email: str, password: str) -> dict:
    try:
        response = await supabase.auth.sign_up({"email": email, "password": password})
    except Exception as e:
        logger.error(
            "Signup exception | type=%s | str=%s | repr=%s | args=%s | attrs=%s",
            type(e).__name__,
            str(e),
            repr(e),
            e.args,
            {k: v for k, v in vars(e).items() if not k.startswith("_")} if vars(e) else {},
        )
        msg = str(e).lower()
        if "already registered" in msg or "already in use" in msg:
            raise HTTPException(status_code=400, detail="Email already registered")
        raise HTTPException(status_code=400, detail="Signup failed. Please check your input.")

    if response.user is None:
        raise HTTPException(status_code=400, detail="Email already registered")
    if response.session is None:
        raise HTTPException(
            status_code=400,
            detail="Email confirmation required. Check your inbox.",
        )

    return {
        "access_token": response.session.access_token,
        "token_type": response.session.token_type,
        "user": {"id": str(response.user.id), "email": response.user.email},
    }


async def login(supabase: AsyncClient, email: str, password: str) -> dict:
    try:
        response = await supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {
        "access_token": response.session.access_token,
        "token_type": response.session.token_type,
        "user": {"id": str(response.user.id), "email": response.user.email},
    }
