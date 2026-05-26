# F-04 요리 완료 처리 — 설계 문서

**날짜:** 2026-05-26  
**기능:** 레시피 채택 시 인벤토리 재고 차감 (α-스코어 우선순위 기반)  
**상태:** 승인됨

---

## 1. 개요

사용자가 레시피를 채택하여 요리를 진행하면, 해당 레시피에 사용된 식재료의 재고를 인벤토리에서 차감한다. 같은 종류의 재고가 여러 행으로 나뉘어 있을 경우, α-스코어 내림차순(우선순위 높은 재고 먼저)으로 순차 차감한다.

---

## 2. 아키텍처

### 신규 파일

| 파일 | 역할 |
|------|------|
| `app/services/cooking_service.py` | 차감 알고리즘 전담 비즈니스 로직 |
| `app/schemas/cooking.py` | 요청/응답 Pydantic 스키마 |

### 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app/routers/recipes.py` | `POST /{recipe_id}/cook` 엔드포인트 추가 |

### 변경 없는 파일

- `app/services/inventory_service.py` — `_clear_bit_if_last` 재사용 (import)
- `app/services/bitset_service.py` — `clear_bit` 재사용 (기존 함수)
- `app/main.py` — 변경 없음 (recipes 라우터 이미 등록됨)

### Worktree

`.worktrees/feature-cooking-completion` (브랜치: `feature/cooking-completion`, master에서 분기)

---

## 3. API 명세

### 엔드포인트

```
POST /recipes/{recipe_id}/cook
Authorization: Bearer <token>
```

### 요청 바디

```json
{
  "ingredients": [
    { "ingredient_master_id": 5, "quantity": 200.0 },
    { "ingredient_master_id": 12, "quantity": 1.0 }
  ]
}
```

- `ingredients`에 포함된 재료만 차감. 레시피에 있더라도 목록에 없으면 차감하지 않음.
- `quantity`: 실제 사용한 수량 (클라이언트가 결정). `recipe_ingredient.quantity`(varchar)는 참고용이며 차감 기준이 아님.

### 응답

```json
{
  "success": true,
  "data": {
    "recipe_id": 7,
    "recipe_name": "닭볶음탕",
    "deductions": [
      {
        "ingredient_master_id": 5,
        "ingredient_name": "닭가슴살",
        "requested": 200.0,
        "deducted": 200.0,
        "rows_affected": [
          { "inventory_id": 12, "deducted": 150.0, "deleted": true },
          { "inventory_id": 18, "deducted": 50.0,  "deleted": false }
        ]
      }
    ]
  },
  "message": "요리가 완료되었습니다."
}
```

- `deducted < requested`: 재고 부족으로 부분 차감됨
- `deleted: true`: 해당 인벤토리 행이 수량 0으로 삭제됨

### 에러 응답

| 상태코드 | 조건 |
|----------|------|
| 401 | 인증 토큰 없음/만료 |
| 404 | `recipe_id` 존재하지 않음 |
| 500 | DB 오류 (트랜잭션 롤백) |

---

## 4. 차감 알고리즘

### 4.1 α-스코어 기반 우선순위 정렬

같은 `ingredient_master_id`의 여러 인벤토리 행을 α-스코어 **내림차순**으로 정렬하여 우선순위가 높은 항목부터 차감.

```python
α = risk_factor × quantity / (D-day² + 1)
D-day = max(1, (expire_date - today).days)
```

같은 재료는 `risk_factor`가 동일하므로, 실질적으로 `quantity / (D-day² + 1)` 내림차순.  
→ 유통기한 임박 + 수량 많은 항목을 먼저 소진.

> **Note:** `docs/algorithms.md` 섹션 4의 FIFO(expire_date 오름차순) 대신 α-스코어 내림차순으로 구현. (사용자 요구사항 우선)

### 4.2 차감 절차 (단일 재료)

```
1. user_ingredient에서 (user_id, ingredient_master_id) 행 전체 조회
2. α-스코어 내림차순 정렬
3. remaining = 요청 수량
4. 각 행 순회:
   a. remaining >= 행.quantity:
      → 행 전체 차감 (DELETE), remaining -= 행.quantity
   b. remaining < 행.quantity:
      → 행 수량 갱신 (UPDATE quantity -= remaining), remaining = 0, 중단
5. remaining > 0 이면 재고 부족 (부분 차감 허용, 계속 진행)
6. 모든 행 처리 후 총 잔여량 = 0이면 Redis BitSet 해당 bit_id 클리어
```

### 4.3 전체 흐름

```
cook_recipe(db, redis, user_id, recipe_id, CookRequest):
  1. recipe 존재 확인 (없으면 404)
  2. ingredient_master_id 목록으로 IngredientMaster 일괄 조회
     → ingredient_name 취득 + bit_id 취득 (N+1 방지)
  3. 재료별 차감 처리 (위 4.2 반복)
     → 잔여량 = 0인 ingredient_master_id를 depleted_ids 집합에 누적
  4. DB 커밋
  5. depleted_ids 순회 → Redis clear_bit (커밋 후 처리, DB 상태와 일치 보장)
  6. CookResult 반환
```

**비트 클리어 방식:** `_clear_bit_if_last`(inventory_service)를 재사용하지 않고,  
차감 루프 중 잔여량을 직접 추적하여 커밋 후 `clear_bit`를 호출.  
이유: 차감 루프에서 이미 잔여량을 알고 있어 추가 DB 조회가 불필요.

---

## 5. Pydantic 스키마 (`app/schemas/cooking.py`)

```python
class IngredientUsage(BaseModel):
    ingredient_master_id: int
    quantity: float

class CookRequest(BaseModel):
    ingredients: list[IngredientUsage]

class InventoryDeduction(BaseModel):
    inventory_id: int
    deducted: float
    deleted: bool

class IngredientDeductionResult(BaseModel):
    ingredient_master_id: int
    ingredient_name: str
    requested: float
    deducted: float
    rows_affected: list[InventoryDeduction]

class CookResult(BaseModel):
    recipe_id: int
    recipe_name: str
    deductions: list[IngredientDeductionResult]
```

---

## 6. 테스트 계획

| 케이스 | 기대 결과 |
|--------|-----------|
| 재고 충분, 단일 행 | deducted == requested, rows_affected 1건 |
| 재고 충분, 복수 행 | α-스코어 순서로 순차 차감, 일부 deleted=true |
| 재고 부족 (부분 차감) | deducted < requested, 남은 재고 행 유지 |
| 재고 완전 소진 | Redis BitSet 해당 비트 0으로 전환 확인 |
| recipe_id 없음 | 404 반환 |
| ingredients 빈 배열 | deductions 빈 배열, 성공 |
| ingredient_master_id 미보유 | deducted=0, rows_affected 빈 배열, 계속 진행 |
