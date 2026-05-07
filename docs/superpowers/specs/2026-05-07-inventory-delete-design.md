# Inventory Delete Design

**Date:** 2026-05-07
**Feature:** 냉장고 재고 식재료 단건 삭제

## Overview

`DELETE /api/v1/inventory/{inventory_id}` 엔드포인트를 추가하고, 서비스 레이어에 `delete_ingredient` 함수를 구현한다. DB 삭제 후 남은 동일 재료 수를 확인해 0이면 Redis bit를 clear한다.

## Architecture

- **Router**: `app/routers/inventory.py` — DELETE 엔드포인트 추가
- **Service**: `app/services/inventory_service.py` — `delete_ingredient` 함수 추가
- **No new models or schemas required**

## Service Logic (`delete_ingredient`)

```
1. db.get(UserInventory, inventory_id) → 없으면 404
2. item.user_id != user_id → 403
3. ingredient_master_id 저장
4. db.delete(item) + db.commit()
5. COUNT remaining WHERE user_id=user_id AND ingredient_master_id=ingredient_master_id
6. if remaining == 0:
     ingredient = db.get(IngredientMaster, ingredient_master_id)
     clear_bit(redis, user_id, ingredient.bit_id)
```

**Approach rationale (Delete-then-Check):** DB 삭제가 먼저 성공해야 Redis bit를 건드리므로, 실패 시 불일치가 "없어야 할 bit 없음"(안전) 방향으로만 발생한다. 현재 `register_ingredient`와 동일한 패턴(DB 먼저, Redis 후처리)을 따른다.

## Router Endpoint

```
DELETE /api/v1/inventory/{inventory_id}
Response: ApiResponse[None] 200
Errors: 404 (not found), 403 (not owner)
```

## Error Handling

| 상황 | HTTP 코드 |
|------|-----------|
| inventory_id 존재하지 않음 | 404 |
| 다른 유저의 항목 | 403 |

## Out of Scope

- 재료 단위 전체 삭제 (ingredient_master_id 기준)
- Soft delete / 삭제 이력 기록
