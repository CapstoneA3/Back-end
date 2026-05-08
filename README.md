# 냉장고 재고 관리 & 레시피 추천 서비스

개인 냉장고의 식재료를 관리하고, 보유 재료 기반으로 최적 레시피를 추천하는 FastAPI 백엔드 서버.

## 해결하는 문제

| 문제 | 해결 방식 |
|------|-----------|
| 수동 입력 번거로움으로 발생하는 실제 재고와 앱 데이터 간의 불일치 | 유통기한 자동 계산 + 신호등 경고 |
| LLM 기반 레시피 추천의 느린 응답 · 높은 운영 비용 | Redis BitSet 비트마스킹으로 O(n) 매칭 |
| 유통기한 임박 식재료 방치 | α-스코어링으로 위험 재료 사용 레시피 우선 노출 |

---

## 기술 스택

| 항목 | 기술 |
|------|------|
| 웹 프레임워크 | FastAPI (Python 3.11+) |
| 마스터/레시피 DB | Supabase (PostgreSQL) |
| ORM | SQLAlchemy async |
| 사용자 인증 | Supabase Auth (JWT Bearer) |
| BitSet 캐시 | Redis |
| 스키마 검증 | Pydantic v2 |

---

## Getting Started

### 1. 의존성 설치

Python 3.11 이상이 필요하다.

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

프로젝트 루트에 `.env.local` 파일을 생성한다.

```env
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>/<db>
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
REDIS_URL=redis://localhost:6379   # 기본값, 생략 가능
```

| 변수 | 필수 | 설명 |
|------|------|------|
| `DATABASE_URL` | Y | PostgreSQL 비동기 연결 문자열 (`postgresql+asyncpg://`) |
| `SUPABASE_URL` | Y | Supabase 프로젝트 URL |
| `SUPABASE_ANON_KEY` | Y | Supabase anon (public) 키 |
| `REDIS_URL` | N | Redis 연결 URL (기본값: `redis://localhost:6379`) |

### 3. 서버 실행

Redis가 로컬에서 실행 중이어야 한다 (`redis-server` 또는 Docker: `docker run -p 6379:6379 redis`).

```bash
uvicorn app.main:app --reload
```

서버가 `http://localhost:8000`에서 시작된다.

### 4. API 문서

| 주소 | 설명 |
|------|------|
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc |
| `http://localhost:8000/health` | 헬스 체크 (`{"status": "ok"}`) |

---

## 인증 (Authentication)

모든 보호된 엔드포인트는 **Supabase Auth** 기반 **JWT Bearer 토큰**이 필요하다.

### 토큰 발급 흐름

1. `POST /api/v1/auth/signup` 또는 `POST /api/v1/auth/login`으로 `access_token` 발급
2. 이후 요청 헤더에 포함:

```http
Authorization: Bearer <access_token>
```

---

### Base URL

```
http://localhost:8000/api/v1
```

---

### POST `/auth/signup` — 회원가입

이메일·비밀번호로 신규 계정을 생성하고 JWT 토큰을 반환한다.

**인증 불필요**

#### 요청 바디

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `email` | string | Y | 이메일 주소 |
| `password` | string | Y | 비밀번호 |

#### 요청 예시

```json
POST /api/v1/auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secret1234"
}
```

#### 응답 예시 (201 Created)

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "user": {
      "id": "uuid-1234-...",
      "email": "user@example.com"
    }
  },
  "message": "회원가입이 완료되었습니다."
}
```

#### 에러 응답

| 상태 | 원인 |
|------|------|
| 400 | 이미 등록된 이메일 또는 잘못된 입력값 |
| 400 | Supabase 이메일 확인이 활성화된 경우 — 이메일 인증 후 재시도 필요 |

---

### POST `/auth/login` — 로그인

이메일·비밀번호로 로그인하고 JWT 토큰을 반환한다.

**인증 불필요**

#### 요청 바디

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `email` | string | Y | 이메일 주소 |
| `password` | string | Y | 비밀번호 |

#### 요청 예시

```json
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secret1234"
}
```

#### 응답 예시 (200 OK)

```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "user": {
      "id": "uuid-1234-...",
      "email": "user@example.com"
    }
  },
  "message": ""
}
```

#### 에러 응답

| 상태 | 원인 |
|------|------|
| 401 | 이메일 또는 비밀번호 불일치 |

---

### GET `/auth/me` — 내 정보 조회

현재 로그인된 사용자의 계정 정보를 반환한다.

**Bearer 토큰 필수**

#### 요청 예시

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

#### 응답 예시 (200 OK)

```json
{
  "success": true,
  "data": {
    "id": "uuid-1234-...",
    "email": "user@example.com",
    "created_at": "2026-05-08T10:00:00+09:00"
  },
  "message": ""
}
```

#### 에러 응답

| 상태 | 원인 |
|------|------|
| 401 | Authorization 헤더 없음 또는 토큰 만료·무효 |
