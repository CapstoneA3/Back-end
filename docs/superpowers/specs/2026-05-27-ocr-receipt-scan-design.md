# OCR 영수증 스캔 → 재고 등록 — 설계 문서

**날짜:** 2026-05-27  
**기능:** 영수증 이미지 OCR 인식 → 식재료 매칭 → 인벤토리 일괄 등록  
**상태:** 승인됨

---

## 1. 개요

사용자가 마트 영수증 이미지를 업로드하면, CLOVA OCR API로 품목명을 추출하고 `ingredient_master` 테이블과 매칭하여 재고 등록 후보를 반환한다. 사용자가 후보를 확인·수정 후 확정하면 인벤토리에 일괄 등록된다.

2-step 플로우:
1. `POST /ocr/scan` — 이미지 → 매칭 후보 반환
2. `POST /ocr/confirm` — 사용자 확정 목록 → 인벤토리 등록

---

## 2. 아키텍처

### 신규 파일

| 파일 | 역할 |
|------|------|
| `app/routers/ocr.py` | `/ocr/scan`, `/ocr/confirm` 엔드포인트 |
| `app/services/ocr_service.py` | CLOVA API 호출, 응답 파싱 |
| `app/services/matching_service.py` | 품목명 → ingredient_master 매칭 (exacte/fuzzy) |
| `app/schemas/ocr.py` | 요청/응답 Pydantic 스키마 |

### 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app/main.py` | `ocr_router` include 추가 |
| `app/core/config.py` | `CLOVA_OCR_URL`, `CLOVA_OCR_SECRET` 설정 추가 |
| `.env.example` | OCR 관련 환경변수 예시 추가 |
| `requirements.txt` | `httpx`, `rapidfuzz` 추가 |

### 테스트 파일 (신규)

| 파일 | 대상 |
|------|------|
| `tests/test_ocr_service.py` | `ocr_service` 단위 테스트 |
| `tests/test_matching_service.py` | `matching_service` 단위 테스트 |
| `tests/test_ocr_router.py` | HTTP 통합 테스트 |

### Worktree

`.worktrees/feature-ocr-scan` (브랜치: `feature/ocr-scan`, master에서 분기)

---

## 3. API 명세

### 3.1 스캔 엔드포인트

```
POST /api/v1/ocr/scan
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**요청:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `image` | file | 영수증 이미지 (jpeg/png/pdf) |

**응답 (200):**

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "raw_text": "닭가슴살200g",
        "recommended_action": "register",
        "candidates": [
          { "ingredient_master_id": 5, "ingredient_name": "닭가슴살", "confidence": 95.2 },
          { "ingredient_master_id": 38, "ingredient_name": "닭날개", "confidence": 72.1 }
        ]
      },
      {
        "raw_text": "계란 10구",
        "recommended_action": "register",
        "candidates": [
          { "ingredient_master_id": 2, "ingredient_name": "달걀", "confidence": 88.5 }
        ]
      },
      {
        "raw_text": "비닐봉투",
        "recommended_action": "skip",
        "candidates": []
      }
    ]
  }
}
```

- `recommended_action: "register"`: 매칭 신뢰도 충분, 등록 권장
- `recommended_action: "skip"`: 매칭 실패 또는 제외 품목 (비닐봉투, 봉지 등)
- `candidates`: 상위 3개 fuzzy 매칭 결과 (confidence 내림차순)

### 3.2 확정 엔드포인트

```
POST /api/v1/ocr/confirm
Authorization: Bearer <token>
Content-Type: application/json
```

**요청:**

```json
{
  "items": [
    { "ingredient_master_id": 5, "quantity": 200.0, "expire_date": "2026-06-10" },
    { "ingredient_master_id": 2, "quantity": 10.0 }
  ]
}
```

- `expire_date` 생략 시 `ingredient_master.default_shelf_days` 기준으로 자동 계산 (기존 `register_ingredient` 동작과 동일)

**응답 (201):**

```json
{
  "success": true,
  "data": {
    "registered": [ /* InventoryRead 배열 */ ],
    "errors": [
      { "ingredient_master_id": 999, "reason": "Ingredient not found" }
    ]
  },
  "message": "재고가 등록되었습니다."
}
```

- partial success 허용: 성공 항목만 등록, 실패 항목은 `errors`에 기록
- `registered`가 비어있어도 `success: true` (사용자가 모두 skip했을 수 있음)

### 에러 응답

| 상태코드 | 조건 |
|----------|------|
| 400 | 지원하지 않는 이미지 포맷 |
| 401 | 인증 토큰 없음/만료 |
| 504 | CLOVA API timeout (5초 초과) |
| 500 | CLOVA 인증 실패 또는 내부 오류 |

---

## 4. 서비스 설계

### 4.1 `ocr_service.scan_receipt`

```python
async def scan_receipt(image_bytes: bytes, filename: str) -> list[OcrRawItem]:
```

- `httpx.AsyncClient`로 CLOVA OCR API에 `multipart/form-data` POST
- timeout: 5초 (`httpx.TimeoutException` → 504 전파)
- 응답 파싱: `images[0].receipt.result.subResults[*].items[*].name.text`
- 빈 결과 → 빈 리스트 반환 (에러 아님)

CLOVA 요청 형식:
```python
{
  "message": {
    "images": [{"format": ext, "name": filename}],
    "requestId": str(uuid4()),
    "version": "V2",
    "timestamp": int(time() * 1000)
  }
}
```
헤더: `X-OCR-SECRET: {CLOVA_OCR_SECRET}`

### 4.2 `matching_service.match_items`

```python
async def match_items(db: AsyncSession, raw_items: list[OcrRawItem]) -> list[OcrScanCandidate]:
```

**매칭 파이프라인:**

1. **전처리**: DB에서 모든 `IngredientMaster` 조회 (id, name, aliases)  
2. **제외 필터**: 비닐봉투, 영수증, 쿠폰 등 키워드 → `recommended_action: "skip"`  
3. **override 테이블**: 하드코딩된 매핑 dict (`"계란" → "달걀"` 등) → exact match 전 치환  
4. **exact match**: `raw_text`가 ingredient_name과 정확히 일치 → confidence 100, `recommended_action: "register"`  
5. **fuzzy match**: `rapidfuzz.process.extract(raw_text, names, limit=3)` → top-3 반환  
   - 최고 confidence ≥ 70 → `recommended_action: "register"`  
   - 최고 confidence < 70 → `recommended_action: "skip"`

### 4.3 `confirm` 흐름

```
for item in request.items:
    try:
        result = await register_ingredient(db, redis, user_id, InventoryCreate(...))
        registered.append(result)
    except HTTPException as e:
        errors.append(OcrConfirmError(ingredient_master_id=item.ingredient_master_id, reason=e.detail))
```

- 각 항목은 독립 트랜잭션 (`register_ingredient` 내부에서 `db.commit()` 호출)
- 한 항목 실패가 다른 항목에 영향 없음 (partial success)
- Redis BitSet 갱신은 기존 `register_ingredient`가 처리

---

## 5. Pydantic 스키마 (`app/schemas/ocr.py`)

```python
from decimal import Decimal
from datetime import date
from typing import Literal
from pydantic import BaseModel

class OcrRawItem(BaseModel):
    text: str

class OcrCandidate(BaseModel):
    ingredient_master_id: int
    ingredient_name: str
    confidence: float

class OcrScanCandidate(BaseModel):
    raw_text: str
    recommended_action: Literal["register", "skip"]
    candidates: list[OcrCandidate]

class OcrScanResult(BaseModel):
    items: list[OcrScanCandidate]

class OcrConfirmItem(BaseModel):
    ingredient_master_id: int
    quantity: Decimal
    expire_date: date | None = None

class OcrConfirmRequest(BaseModel):
    items: list[OcrConfirmItem]

class OcrConfirmError(BaseModel):
    ingredient_master_id: int
    reason: str

class OcrConfirmResult(BaseModel):
    registered: list  # list[InventoryRead] — 순환 import 방지를 위해 runtime에서 타입 결정
    errors: list[OcrConfirmError]
```

---

## 6. 설정 (`app/core/config.py`)

```python
CLOVA_OCR_URL: str = ""      # Naver CLOVA OCR API invoke URL
CLOVA_OCR_SECRET: str = ""   # X-OCR-SECRET 헤더값
```

`.env.example`에 추가:
```
CLOVA_OCR_URL=https://...
CLOVA_OCR_SECRET=your-secret
```

---

## 7. 에러 처리

| 상황 | 처리 |
|------|------|
| CLOVA timeout (5초) | `httpx.TimeoutException` → 504 Gateway Timeout |
| CLOVA 인증 실패 (401/403) | 500 Internal Server Error (서버 설정 문제) |
| 지원하지 않는 이미지 포맷 | CLOVA 에러 응답 → 400 Bad Request |
| OCR 인식 품목 없음 | 200 OK, `items: []` |
| confirm 중 특정 ingredient_master_id 없음 | 해당 항목 skip → `errors` 배열에 포함, 나머지 계속 등록 |

---

## 8. 테스트 계획

### `test_ocr_service.py` (CLOVA mock)

| 케이스 | 기대 결과 |
|--------|-----------|
| 정상 영수증 응답 | `OcrRawItem` 리스트 파싱 정확 |
| 빈 subResults | 빈 리스트 반환 |
| httpx.TimeoutException | 예외 전파 |

### `test_matching_service.py` (DB mock)

| 케이스 | 기대 결과 |
|--------|-----------|
| exact match | confidence 100, `recommended_action: "register"` |
| override 히트 (`계란` → `달걀`) | exact match로 처리 |
| fuzzy 매칭 (confidence ≥ 70) | top-3 반환, `recommended_action: "register"` |
| fuzzy 매칭 (confidence < 70) | `recommended_action: "skip"` |
| 제외 키워드 (`비닐봉투`) | `recommended_action: "skip"`, candidates 빈 배열 |

### `test_ocr_router.py` (service mock)

| 케이스 | 기대 결과 |
|--------|-----------|
| `POST /ocr/scan` 정상 | 200, `items` 배열 반환 |
| `POST /ocr/scan` timeout | 504 응답 |
| `POST /ocr/confirm` 전체 성공 | 201, `registered` 배열, `errors: []` |
| `POST /ocr/confirm` partial success | 201, 일부 `registered`, `errors` 있음 |
