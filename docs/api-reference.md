# API 레퍼런스

> 구현 완료 기준 (2026-05-06). 미구현 엔드포인트는 `api-conventions.md` 참고.

---

## 기본 정보

| 항목 | 값 |
|------|-----|
| Base URL | `http://localhost:8000/api/v1` |
| 프로토콜 | HTTP/1.1 |
| 인코딩 | UTF-8 |
| 응답 형식 | `application/json` |

---

## 인증

Supabase Auth 기반 JWT Bearer 토큰 방식.  
`POST /api/v1/auth/signup` 또는 `POST /api/v1/auth/login`으로 발급받은 `access_token`을 사용합니다.

| 헤더 | 필수 여부 | 설명 |
|------|-----------|------|
| `Authorization` | 조건부 필수 | `/inventory`, `/auth/me` 엔드포인트에 필요. 형식: `Bearer <access_token>` |

**에러 (헤더 누락)**
```json
HTTP 401
{
  "detail": "Authorization header required"
}
```

---

## 공통 응답 형식

### 성공
```json
{
  "success": true,
  "data": { ... },
  "message": "string"
}
```

### 실패
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
| 400 | 잘못된 요청 (유효성 검사 실패) |
| 401 | 인증 헤더 누락 |
| 404 | 리소스 없음 |
| 422 | 요청 바디 파싱 실패 |
| 500 | 서버 내부 오류 |

---

## 식재료 마스터 (Ingredients)

### GET `/api/v1/ingredients` — 식재료 목록 조회

`ingredient_master` 테이블 전체 또는 필터링된 목록을 반환합니다. 인증 불필요.

#### 쿼리 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `q` | string | N | 식재료명 부분 검색 (대소문자 무시) |
| `category` | string | N | 카테고리 정확 일치 필터 |

**카테고리 허용값**

`곡류/면/떡`, `육류`, `생선/해산물`, `채소`, `계란/콩/두부`, `유제품/치즈`, `김치/절임/묵`, `해조류/건어물`, `과일/견과`, `가공식품/기타`, `조미료`

#### 요청 예시
```
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

결과가 없으면 `data: []` 로 반환합니다 (404 아님).

---

### GET `/api/v1/ingredients/{id}` — 식재료 단건 조회

`ingredient_master.id` 기준 단건 조회. 인증 불필요.

#### 경로 파라미터

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `id` | integer | 식재료 PK |

#### 요청 예시
```
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

#### 에러 응답 (404)
```json
{
  "detail": "Ingredient not found"
}
```

---

## 재고 (Inventory)

> 모든 `/inventory` 엔드포인트는 `X-User-ID` 헤더가 필수입니다.

### POST `/api/v1/inventory` — 재고 등록 (F-01)

사용자의 냉장고에 식재료를 등록합니다. DB 저장과 동시에 Redis BitSet의 해당 `bit_id`를 1로 갱신합니다.

- `expire_date` 미입력 시 `ingredient_master.default_shelf_days` 기준으로 자동 계산 (오늘 + default_shelf_days)
- `unit` 미입력 시 기본값 `"개"` 적용

#### 요청 헤더

| 헤더 | 필수 | 값 예시 |
|------|------|---------|
| `X-User-ID` | Y | `user-uuid-1234` |
| `Content-Type` | Y | `application/json` |

#### 요청 바디

| 필드 | 타입 | 필수 | 제약 | 설명 |
|------|------|------|------|------|
| `ingredient_master_id` | integer | Y | — | 등록할 식재료 ID |
| `quantity` | number | N | `> 0`, 기본값 `1` | 수량 |
| `unit` | string | N | — | 단위 (미입력 시 `"개"`) |
| `expire_date` | date | N | `YYYY-MM-DD` | 유통기한 (미입력 시 자동 계산) |

#### 요청 예시
```json
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
    "user_id": "user-uuid-1234",
    "ingredient_master_id": 42,
    "quantity": "6",
    "unit": "개",
    "expire_date": "2026-05-27",
    "created_at": "2026-05-06T10:00:00+09:00",
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
| 401 | `X-User-ID` 헤더 누락 또는 빈 값 |
| 404 | `ingredient_master_id`에 해당하는 식재료 없음 |
| 422 | 요청 바디 형식 오류 (`quantity ≤ 0` 등) |

---

### GET `/api/v1/inventory` — 재고 대시보드 (F-02)

현재 사용자의 전체 재고 목록을 신호등 분류 및 α-스코어와 함께 반환합니다.

#### 요청 헤더

| 헤더 | 필수 | 값 예시 |
|------|------|---------|
| `X-User-ID` | Y | `user-uuid-1234` |

#### 쿼리 파라미터

| 파라미터 | 타입 | 기본값 | 허용값 | 설명 |
|----------|------|--------|--------|------|
| `sort` | string | `recommended` | `recommended`, `expire_date` | 정렬 기준 |

**정렬 기준 상세**

| 값 | 정렬 방식 |
|----|-----------|
| `recommended` | α-스코어 내림차순 (폐기 위험 높은 순) |
| `expire_date` | 유통기한 오름차순 (임박한 순) |

**신호등(traffic_light) 분류 기준**

| 색상 | 조건 |
|------|------|
| `red` | D-day ≤ 2, 또는 (D-day ≤ 5 이고 risk_factor ≥ 2) |
| `yellow` | D-day ≤ 5, 또는 (D-day ≤ 10 이고 risk_factor ≥ 2) |
| `green` | 그 외 |

**α-스코어 공식**

```
score = risk_factor × quantity / (D-day² + 1)
D-day = max(1, expire_date - 오늘)
```

#### 요청 예시
```
GET /api/v1/inventory?sort=recommended
X-User-ID: user-uuid-1234
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
        "user_id": "user-uuid-1234",
        "ingredient_master_id": 42,
        "quantity": "6",
        "unit": "개",
        "expire_date": "2026-05-08",
        "created_at": "2026-05-06T10:00:00+09:00",
        "ingredient": {
          "id": 42,
          "bit_id": 41,
          "name": "계란",
          "category": "계란/콩/두부",
          "default_shelf_days": 21,
          "risk_factor": "2.00"
        },
        "traffic_light": "red",
        "score": 12.0
      },
      {
        "id": 88,
        "user_id": "user-uuid-1234",
        "ingredient_master_id": 10,
        "quantity": "500",
        "unit": "g",
        "expire_date": "2026-05-20",
        "created_at": "2026-05-05T09:00:00+09:00",
        "ingredient": {
          "id": 10,
          "bit_id": 9,
          "name": "닭가슴살",
          "category": "육류",
          "default_shelf_days": 3,
          "risk_factor": "3.00"
        },
        "traffic_light": "green",
        "score": 2.1
      }
    ]
  },
  "message": ""
}
```

재고가 없으면 `data: { "total": 0, "items": [] }` 로 반환합니다.

#### 에러 응답

| 상태 | 원인 |
|------|------|
| 401 | `X-User-ID` 헤더 누락 또는 빈 값 |
| 422 | `sort` 파라미터 허용값 외 값 입력 |

---

## 스키마 정의

### ApiResponse\<T\>

| 필드 | 타입 | 설명 |
|------|------|------|
| `success` | boolean | 항상 `true` |
| `data` | T \| null | 응답 데이터 |
| `message` | string | 보조 메시지 (빈 문자열 가능) |

### ApiErrorResponse

| 필드 | 타입 | 설명 |
|------|------|------|
| `success` | boolean | 항상 `false` |
| `error.code` | string | 에러 코드 |
| `error.message` | string | 에러 설명 |

### IngredientMasterRead

| 필드 | 타입 | Nullable | 설명 |
|------|------|----------|------|
| `id` | integer | N | PK |
| `bit_id` | integer | N | BitSet 인덱스 (0~426) |
| `name` | string | N | 식재료명 |
| `category` | string | N | 카테고리 |
| `default_shelf_days` | integer | Y | 표준 유통기한 (일) |
| `risk_factor` | string (decimal) | N | 위험가중치 α (`"0.10"` / `"1.00"` / `"2.00"` / `"3.00"`) |

### InventoryCreate

| 필드 | 타입 | Nullable | 기본값 | 설명 |
|------|------|----------|--------|------|
| `ingredient_master_id` | integer | N | — | 식재료 PK (필수) |
| `quantity` | number | N | `1` | 수량 (`> 0`) |
| `unit` | string | Y | `"개"` | 단위 |
| `expire_date` | date | Y | 자동 계산 | `YYYY-MM-DD` |

### InventoryRead

| 필드 | 타입 | Nullable | 설명 |
|------|------|----------|------|
| `id` | integer | N | PK |
| `user_id` | string | N | 사용자 ID |
| `ingredient_master_id` | integer | N | 식재료 FK |
| `quantity` | string (decimal) | N | 보유 수량 |
| `unit` | string | Y | 단위 |
| `expire_date` | date | N | 유통기한 |
| `created_at` | datetime | N | 등록 시각 (ISO 8601) |
| `ingredient` | IngredientMasterRead | N | 식재료 상세 정보 |
| `traffic_light` | string | N | `"red"` / `"yellow"` / `"green"` |
| `score` | number | N | α-스코어 (소수점 이하 수 자리) |

### InventoryDashboard

| 필드 | 타입 | 설명 |
|------|------|------|
| `items` | InventoryRead[] | 재고 항목 목록 |
| `total` | integer | 전체 항목 수 |
