from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    email: str = Field(description="사용자 이메일 주소", examples=["user@example.com"])
    password: str = Field(description="비밀번호 (Supabase 정책: 최소 6자)", examples=["secret123"])

    model_config = {
        "json_schema_extra": {
            "example": {"email": "user@example.com", "password": "secret123"}
        }
    }


class LoginRequest(BaseModel):
    email: str = Field(description="가입 시 사용한 이메일 주소", examples=["user@example.com"])
    password: str = Field(description="비밀번호", examples=["secret123"])

    model_config = {
        "json_schema_extra": {
            "example": {"email": "user@example.com", "password": "secret123"}
        }
    }


class UserInfo(BaseModel):
    id: str = Field(description="사용자 UUID (Supabase Auth)")
    email: str = Field(description="사용자 이메일")


class TokenResponse(BaseModel):
    access_token: str = Field(description="JWT 액세스 토큰")
    refresh_token: str = Field(description="리프레시 토큰 (액세스 토큰 갱신용)")
    token_type: str = Field(description="토큰 타입 (항상 'bearer')", examples=["bearer"])
    user: UserInfo


class RefreshRequest(BaseModel):
    refresh_token: str = Field(description="로그인 시 발급받은 리프레시 토큰")

    model_config = {
        "json_schema_extra": {
            "example": {"refresh_token": "<your-refresh-token>"}
        }
    }


class RefreshTokenResponse(BaseModel):
    access_token: str = Field(description="새로 발급된 JWT 액세스 토큰")
    refresh_token: str = Field(description="새로 발급된 리프레시 토큰")
    token_type: str = Field(description="토큰 타입 (항상 'bearer')", examples=["bearer"])


class MeResponse(BaseModel):
    id: str = Field(description="사용자 UUID")
    email: str = Field(description="사용자 이메일")
    created_at: str = Field(description="계정 생성일시 (ISO 8601)")
