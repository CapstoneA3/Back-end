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

---

## 식재료 마스터 API (Ingredients)

`ingredient_master` 테이블 기반. 427개 식재료, 11개 카테고리. **인증 불필요.**

### GET `/ingredients` — 목록 조회 / 검색

#### 쿼리 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `q` | string | N | 식재료명 부분 검색 (대소문자 무시) |
| `category` | string | N | 카테고리 정확 일치 필터 |

**카테고리 허용값**

`곡류/면/떡` · `육류` · `생선/해산물` · `채소` · `계란/콩/두부` · `유제품/치즈` · `김치/절임/묵` · `해조류/건어물` · `과일/견과` · `가공식품/기타` · `조미료`

#### 요청 예시

```http
GET /api/v1/ingredients?q=계란&category=계란/콩/두부
```

#### 응답 예시 (200 OK)

```json
{
  "success": true,
  "data": [
    {
      "id": 42,
      "bit_id": 41,
      "name": "계란",
      "category": "계란/콩/두부",
      "default_shelf_days": 21,
      "risk_factor": "2.00"
    }
  ],
  "message": ""
}
```

결과 없으면 `data: []` 반환 (404 아님).

---

### GET `/ingredients/{id}` — 단건 조회

#### 경로 파라미터

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `id` | integer | 식재료 PK |

#### 요청 예시

```http
GET /api/v1/ingredients/42
```

#### 응답 예시 (200 OK)

```json
{
  "success": true,
  "data": {
    "id": 42,
    "bit_id": 41,
    "name": "계란",
    "category": "계란/콩/두부",
    "default_shelf_days": 21,
    "risk_factor": "2.00"
  },
  "message": ""
}
```

#### 에러 응답

| 상태 | 원인 |
|------|------|
| 404 | 존재하지 않는 id |

---

## 재고 API (Inventory)

사용자 냉장고 재고 관리. **모든 엔드포인트에 Bearer 토큰 필수.**

### POST `/inventory` — 재고 등록 (F-01)

냉장고에 식재료를 등록한다. DB 저장과 동시에 Redis BitSet의 해당 `bit_id`를 1로 갱신한다.

- `expire_date` 생략 시 `default_shelf_days` 기준으로 자동 계산 (오늘 + default_shelf_days)
- `unit` 생략 시 기본값 `"개"` 적용

#### 요청 헤더

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

#### 요청 바디

| 필드 | 타입 | 필수 | 제약 | 설명 |
|------|------|------|------|------|
| `ingredient_master_id` | integer | Y | — | 등록할 식재료 ID |
| `quantity` | number | N | `> 0`, 기본값 `1` | 수량 |
| `unit` | string | N | — | 단위 (기본값 `"개"`) |
| `expire_date` | date | N | `YYYY-MM-DD` | 유통기한 (생략 시 자동 계산) |

#### 요청 예시

```json
POST /api/v1/inventory
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

{
  "ingredient_master_id": 42,
  "quantity": 6,
  "unit": "개",
  "expire_date": "2026-05-27"
}
```

#### 응답 예시 (201 Created)

```json
{
  "success": true,
  "data": {
    "id": 101,
    "user_id": "uuid-1234-...",
    "ingredient_master_id": 42,
    "quantity": "6",
    "unit": "개",
    "expire_date": "2026-05-27",
    "created_at": "2026-05-08T10:00:00+09:00",
    "ingredient": {
      "id": 42,
      "bit_id": 41,
      "name": "계란",
      "category": "계란/콩/두부",
      "default_shelf_days": 21,
      "risk_factor": "2.00"
    },
    "traffic_light": "green",
    "score": 0.0
  },
  "message": "재료가 등록되었습니다."
}
```

#### 에러 응답

| 상태 | 원인 |
|------|------|
| 401 | Authorization 헤더 누락 또는 토큰 만료·무효 |
| 404 | `ingredient_master_id`에 해당하는 식재료 없음 |
| 422 | 요청 바디 파싱 실패 (`quantity ≤ 0` 등) |

---

### GET `/inventory` — 재고 대시보드 (F-02)

현재 사용자의 전체 재고 목록을 신호등 분류 및 α-스코어와 함께 반환한다.

#### 요청 헤더

```http
Authorization: Bearer <access_token>
```

#### 쿼리 파라미터

| 파라미터 | 타입 | 기본값 | 허용값 | 설명 |
|----------|------|--------|--------|------|
| `sort` | string | `recommended` | `recommended`, `expire_date` | 정렬 기준 |

| `sort` 값 | 정렬 방식 |
|-----------|-----------|
| `recommended` | α-스코어 내림차순 (폐기 위험 높은 순) |
| `expire_date` | 유통기한 오름차순 (임박한 순) |

#### 신호등(traffic_light) 분류 기준

| 값 | 조건 |
|----|------|
| `red` | D-day ≤ 2, 또는 D-day ≤ 5이고 risk_factor ≥ 2 |
| `yellow` | D-day ≤ 5, 또는 D-day ≤ 10이고 risk_factor ≥ 2 |
| `green` | 그 외 |

#### α-스코어 공식

```
score = risk_factor × quantity / (D-day² + 1)
D-day = max(1, expire_date − 오늘)
```

#### 요청 예시

```http
GET /api/v1/inventory?sort=recommended
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

#### 응답 예시 (200 OK)

```json
{
  "success": true,
  "data": {
    "total": 2,
    "items": [
      {
        "id": 101,
        "user_id": "uuid-1234-...",
        "ingredient_master_id": 42,
        "quantity": "6",
        "unit": "개",
        "expire_date": "2026-05-10",
        "created_at": "2026-05-08T10:00:00+09:00",
        "ingredient": {
          "id": 42, "bit_id": 41, "name": "계란",
          "category": "계란/콩/두부", "default_shelf_days": 21, "risk_factor": "2.00"
        },
        "traffic_light": "red",
        "score": 12.0
      }
    ]
  },
  "message": ""
}
```

재고 없으면 `data: { "total": 0, "items": [] }` 반환.

#### 에러 응답

| 상태 | 원인 |
|------|------|
| 401 | Authorization 헤더 누락 또는 토큰 만료·무효 |
| 422 | `sort` 파라미터 허용값 외 값 |

---

### PATCH `/inventory/{id}` — 재고 수정 (F-05)

재고 항목의 수량·단위·유통기한을 부분 수정한다. 전달한 필드만 업데이트된다.

> **주의:** `quantity=0` 전달 시 해당 항목이 삭제된다.

#### 경로 파라미터

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `id` | integer | 재고 항목 PK |

#### 요청 헤더

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

#### 요청 바디 (모든 필드 선택)

| 필드 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `quantity` | number | `≥ 0` | 수량 (`0`이면 항목 삭제) |
| `unit` | string | — | 단위 |
| `expire_date` | date | `YYYY-MM-DD` | 유통기한 |

#### 요청 예시

```json
PATCH /api/v1/inventory/101
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

{
  "quantity": 4,
  "expire_date": "2026-05-30"
}
```

#### 응답 예시 (200 OK)

```json
{
  "success": true,
  "data": null,
  "message": "재고가 수정되었습니다."
}
```

#### 에러 응답

| 상태 | 원인 |
|------|------|
| 401 | Authorization 헤더 누락 또는 토큰 만료·무효 |
| 403 | 다른 사용자 소유의 재고 항목 |
| 404 | 존재하지 않는 inventory id |

---

### DELETE `/inventory/{id}` — 재고 삭제 (F-05)

재고 항목을 삭제한다. 해당 재료의 잔여 재고가 0이 되면 Redis BitSet의 `bit_id`를 0으로 전환한다.

#### 경로 파라미터

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `id` | integer | 재고 항목 PK |

#### 요청 예시

```http
DELETE /api/v1/inventory/101
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

#### 응답 예시 (200 OK)

```json
{
  "success": true,
  "data": null,
  "message": "재료가 삭제되었습니다."
}
```

#### 에러 응답

| 상태 | 원인 |
|------|------|
| 401 | Authorization 헤더 누락 또는 토큰 만료·무효 |
| 403 | 다른 사용자 소유의 재고 항목 |
| 404 | 존재하지 않는 inventory id |

---

## 레시피 API — 예정 (Recipes)

> 아직 구현되지 않은 엔드포인트입니다. 명세만 기술합니다.

| 메서드 | 경로 | 설명 | 기능 |
|--------|------|------|------|
| GET | `/api/v1/recipes` | 추천 레시피 목록 | 비트마스킹 + α-스코어 정렬 (F-03) |
| GET | `/api/v1/recipes/{id}` | 레시피 상세 조회 | — |
| POST | `/api/v1/recipes/{id}/complete` | 요리 완료 처리 | FIFO 재고 차감 + BitSet 갱신 (F-04) |

### GET `/recipes` — 추천 레시피 목록 (F-03)

사용자 보유 재료 BitSet과 각 레시피의 `requirement_mask`를 AND 연산하여 조리 가능 레시피를 필터링하고, α-스코어 내림차순으로 정렬해 반환한다.

**Bearer 토큰 필수**

### POST `/recipes/{id}/complete` — 요리 완료 처리 (F-04)

레시피 재료를 FIFO(expire_date 오름차순) 방식으로 재고에서 차감한다. 소진된 재료는 BitSet에서 해당 비트를 0으로 전환한다.

**Bearer 토큰 필수**

---

## 공통 응답 스키마

### 성공 응답

```json
{
  "success": true,
  "data": { },
  "message": "string"
}
```

### 실패 응답

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "설명"
  }
}
```

### HTTP 상태 코드

| 코드 | 의미 |
|------|------|
| 200 | 조회 성공 |
| 201 | 생성 성공 |
| 400 | 잘못된 요청 |
| 401 | 인증 실패 (헤더 누락 또는 토큰 만료) |
| 403 | 권한 없음 (타인 소유 리소스) |
| 404 | 리소스 없음 |
| 422 | 요청 바디 파싱 실패 |
| 500 | 서버 내부 오류 |

---

## 핵심 알고리즘

### 1. BitSet 구조

각 식재료는 `ingredient_master.bit_id` (0~426)를 인덱스로 Redis에 비트 배열로 캐싱된다. 보유하면 1, 미보유면 0.

```
예) bit_id=0 (쌀) 보유, bit_id=2 (계란) 보유, bit_id=5 (우유) 미보유
→ ...001 0101  (이진수)
```

- Redis 키: `user:{user_id}:bitset`
- 갱신 시점: 재료 추가 / 재료 삭제 / 요리 완료

---

### 2. 비트마스킹 레시피 매칭

각 레시피는 필요 재료의 `bit_id` 집합으로 구성된 `requirement_mask`를 보유한다. AND 연산으로 조리 가능 여부를 O(1)에 판단한다.

```python
# 조리 가능 조건
(user_bitset & recipe_mask) == recipe_mask

# requirement_mask 생성
mask = 0
for ingredient in recipe.ingredients:
    mask |= (1 << ingredient.bit_id)
```

전체 레시피 순회는 O(n).

---

### 3. α-스코어링 레시피 우선순위 정렬

조리 가능 레시피 중 **폐기 위험이 높은 재료를 먼저 소비**할 수 있는 레시피를 상위에 노출한다.

```
# 재료별 스코어
score_ingredient = α × quantity / (D-day² + 1)

# 레시피 스코어 합산
score_recipe = Σ score_ingredient  (레시피에 포함된 보유 재료 전체)

- α     : risk_factor (0.1 / 1 / 2 / 3)
- D-day : max(1, expire_date − 오늘)
```

**risk_factor (α) 기준 (FDA)**

| α | 분류 | 예시 |
|---|------|------|
| 3 | 육류·어패류·유제품 | 고기, 생선, 우유 |
| 2 | 고수분·가열 식품 | 딸기, 두부, 베이컨 |
| 1 | 장기 보관 가능 농산물 | 감자, 양파, 사과 |
| 0.1 | 저수분·건조 가공식품 | 쌀, 파스타면, 조미료 |

---

### 4. FIFO 재고 차감

'요리 완료' 시 레시피 재료를 `expire_date` 오름차순(선입선출)으로 차감한다.

```
1. recipe_ingredient 목록 조회
2. 각 재료별 user_inventory → expire_date 오름차순 정렬
3. 필요 수량만큼 순차 차감; 수량 0이 되면 해당 row 삭제
4. 재고 완전 소진 시 BitSet Bit-Flip:
   if sum(remaining quantity) == 0:
       user_bitset &= ~(1 << bit_id)  # 해당 비트 OFF
```

---

## 구현 현황

| 기능 ID | 기능 | 엔드포인트 | 상태 |
|---------|------|-----------|------|
| — | 인증 (회원가입·로그인·내 정보) | `POST /auth/signup`, `POST /auth/login`, `GET /auth/me` | ✅ 완료 |
| — | 식재료 마스터 조회 | `GET /ingredients`, `GET /ingredients/{id}` | ✅ 완료 |
| F-01 | 식재료 등록 | `POST /inventory` | ✅ 완료 |
| F-02 | 재고 대시보드 (신호등 + α-스코어) | `GET /inventory` | ✅ 완료 |
| F-03 | 레시피 추천 (비트마스킹 + α-스코어 정렬) | `GET /recipes` | 🔲 예정 |
| F-04 | 요리 완료 처리 (FIFO 차감) | `POST /recipes/{id}/complete` | 🔲 예정 |
| F-05 | 재고 수정·삭제 | `PATCH /inventory/{id}`, `DELETE /inventory/{id}` | ✅ 완료 |

### 보류 기능

| 기능 | 설명 |
|------|------|
| OCR 영수증 인식 | 영수증 촬영으로 식재료 일괄 등록 |
