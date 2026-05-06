# Auth 설계 스펙

**날짜**: 2026-05-06
**상태**: 승인됨
**범위**: 회원가입, 로그인, 마이페이지, 기존 inventory 인증 연동

---

## 배경 및 목표

현재 `/api/v1/inventory` 엔드포인트는 `X-User-ID` 헤더를 통한 임시 인증을 사용하고 있다. 이를 Supabase Auth 기반의 JWT 인증으로 교체하고, 회원가입/로그인/마이페이지 API를 추가한다.

**결정 사항**
- 인증 제공자: Supabase Auth
- 로그인 방식: 이메일/비밀번호
- 별도 `users` 테이블: 없음 (Supabase Auth `auth.users`만 사용)
- 소셜 로그인: 미포함 (향후 추가 가능)

---

## 아키텍처

### 신규 파일

| 파일 | 역할 |
|------|------|
| `app/core/supabase_client.py` | supabase-py 클라이언트 싱글톤 초기화 |
| `app/routers/auth.py` | `/auth/signup`, `/auth/login`, `/auth/me` 엔드포인트 |
| `app/services/auth_service.py` | Supabase Auth 호출 비즈니스 로직 |
| `app/schemas/auth.py` | 요청/응답 Pydantic 스키마 |

### 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app/dependencies/auth.py` | `X-User-ID` 헤더 → `Authorization: Bearer` JWT 검증으로 교체 |
| `app/core/config.py` | `SUPABASE_URL`, `SUPABASE_ANON_KEY` 설정 필드 추가 |
| `app/main.py` | auth 라우터 등록 |
| `.env` | `SUPABASE_URL`, `SUPABASE_ANON_KEY` 값 추가 |
| `requirements.txt` | `supabase` 패키지 추가 |

### 변경 없는 파일

`app/routers/inventory.py`, `app/services/inventory_service.py` — `get_current_user_id()` 반환값(UUID 문자열)이 동일하게 유지되므로 수정 불필요.

---

## 엔드포인트 명세

### POST `/api/v1/auth/signup` — 회원가입

인증 불필요.

**요청 바디**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**응답 (201 Created)**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "user": {
      "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "email": "user@example.com"
    }
  },
  "message": "회원가입이 완료되었습니다."
}
```

**에러**

| 상태 | 원인 |
|------|------|
| 400 | 이메일 중복 (`Email already registered`) |
| 400 | 비밀번호 6자 미만 (`Password should be at least 6 characters`) |
| 422 | 요청 바디 형식 오류 |

---

### POST `/api/v1/auth/login` — 로그인

인증 불필요.

**요청 바디**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**응답 (200 OK)**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "user": {
      "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "email": "user@example.com"
    }
  },
  "message": ""
}
```

**에러**

| 상태 | 원인 |
|------|------|
| 401 | 이메일 또는 비밀번호 불일치 (`Invalid email or password`) |
| 422 | 요청 바디 형식 오류 |

---

### GET `/api/v1/auth/me` — 마이페이지

`Authorization: Bearer <access_token>` 헤더 필수.

Supabase Auth `get_user(token)` 를 호출하여 사용자 정보를 반환한다. 별도 DB 쿼리 없음.

**응답 (200 OK)**
```json
{
  "success": true,
  "data": {
    "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "email": "user@example.com",
    "created_at": "2026-05-06T10:00:00+09:00"
  },
  "message": ""
}
```

**에러**

| 상태 | 원인 |
|------|------|
| 401 | 토큰 만료 또는 변조 (`Invalid or expired token`) |
| 401 | Authorization 헤더 누락 (`Authorization header required`) |

---

## 인증 의존성 교체

### 현재 (`X-User-ID` 헤더)
```python
async def get_current_user_id(x_user_id: str = Header(..., alias="X-User-ID")) -> str:
    ...
```

### 변경 후 (Bearer JWT)
```python
async def get_current_user_id(
    authorization: str = Header(..., alias="Authorization")
) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    response = supabase.auth.get_user(token)   # Supabase가 서명 검증
    return str(response.user.id)               # UUID → str, 기존 코드와 동일
```

`user_inventory.user_id` 컬럼 타입(`String`)은 변경 없음. Supabase Auth의 UUID를 문자열로 저장.

---

## 환경변수

`.env`에 아래 두 항목 추가 필요. Supabase 콘솔 → Project Settings → API에서 확인.

| 키 | 예시 | 설명 |
|----|------|------|
| `SUPABASE_URL` | `https://xxxxxxxxxxx.supabase.co` | 프로젝트 URL |
| `SUPABASE_ANON_KEY` | `eyJ...` | 공개 anon 키 |

`SUPABASE_ANON_KEY`는 공개 키이므로 Git에 커밋해도 무방하나, 일관성을 위해 `.env`에서 관리한다.

---

## 패키지 의존성

`requirements.txt`에 추가:
```
supabase==2.29.0   # supabase-py, auth + storage 클라이언트 포함
```

`python-dotenv`는 이미 설치되어 있어 별도 추가 불필요.

---

## 데이터 흐름 요약

```
[회원가입/로그인]
클라이언트
  → POST /api/v1/auth/signup|login  (email, password)
  → auth_service.signup()|login()
  → supabase.auth.sign_up()|sign_in_with_password()
  → Supabase Auth 처리
  ← access_token (JWT) + user.id, user.email

[보호된 엔드포인트]
클라이언트
  → Authorization: Bearer <access_token>
  → get_current_user_id()
  → supabase.auth.get_user(token)   ← Supabase 서명 검증
  → user.id 추출 (UUID str)
  → inventory_service 등 기존 로직 그대로

[마이페이지]
클라이언트
  → GET /api/v1/auth/me  (Bearer token)
  → get_current_user_id() 와 동일하게 get_user(token) 호출
  → id, email, created_at 반환  ← DB 조회 없음
```

---

## 제외 범위

- 토큰 갱신(`refresh_token`) 엔드포인트: 프론트엔드가 Supabase SDK 자체 갱신 로직 사용 권장
- 로그아웃 엔드포인트: 클라이언트 측 토큰 삭제로 처리 (서버 세션 없음)
- 이메일 인증 확인 플로우: Supabase 기본 동작(이메일 발송)에 위임
- 소셜 로그인: 향후 `auth_service.py` 내 메서드 추가로 확장 가능
