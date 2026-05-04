# 기능 명세 및 우선순위

## MVP 기능 (1차 구현 대상)

### F-01. 식재료 등록

사용자가 카테고리 아이콘 선택 또는 텍스트 검색으로 `ingredient_master`에서 재료를 찾아 냉장고에 추가.

**처리 흐름**
1. 사용자가 재료 선택
2. `ingredient_master.default_shelf_days` 기반으로 `expire_date` 자동 계산 (오늘 + default_shelf_days)
3. 수량/단위 입력 후 `user_inventory`에 저장
4. Redis BitSet의 해당 `bit_id`를 1로 갱신

**입력**
- 재료 선택 (ingredient_master_id)
- 수량, 단위 (선택, 기본값 제공)
- expire_date (자동 세팅, 사용자 수정 가능)

---

### F-02. 재고 대시보드

사용자의 `user_inventory` 전체 조회 후 신호등 분류 및 정렬하여 반환.

**처리 흐름**
1. `user_inventory` 전체 조회
2. 각 항목에 신호등 분류 적용 (빨강/노랑/초록)
3. 정렬 방식에 따라 반환

**정렬 옵션**
- `recommended`: α-스코어 기준 내림차순 (폐기 위험 높은 순)
- `expire_date`: 유통기한 오름차순

---

### F-03. 레시피 추천

Redis BitSet 기반 비트마스킹으로 조리 가능 레시피 필터링 후 α-스코어 정렬하여 랭킹 반환.

**처리 흐름**
1. Redis에서 `user_bitset` 로드
2. 전체 레시피의 `requirement_mask`와 AND 연산으로 조리 가능 목록 추출
3. α-스코어링으로 레시피 우선순위 산출
4. 상위 N개 반환 (N 미확정)

> 알고리즘 상세: `docs/algorithms.md` 2·3항 참고

---

### F-04. 요리 완료 처리

'요리 완료' 이벤트 발생 시 레시피 재료를 FIFO 방식으로 `user_inventory`에서 차감.

**처리 흐름**
1. 레시피의 `recipe_ingredient` 목록 조회
2. 각 재료를 FIFO (expire_date 오름차순) 순서로 차감
3. 재고 소진 재료 → Redis BitSet Bit-Flip
4. 사용자가 실제 사용량 수정한 경우 수정된 수량 기준으로 차감

> 알고리즘 상세: `docs/algorithms.md` 4항 참고

---

### F-05. 식재료 수동 수정/삭제

사용자가 재고 항목을 직접 수정하거나 삭제.

**수정 가능 항목**: 수량, 단위, expire_date

**처리 흐름 (삭제 시)**
1. `user_inventory` 해당 항목 삭제
2. 같은 `ingredient_master_id`의 잔여 재고가 0이면 Redis BitSet Bit-Flip

---

## 보류 기능 (추후 구현)

| 기능 | 설명 | 비고 |
|------|------|------|
| OCR 영수증 인식 | 영수증 촬영으로 식재료 일괄 등록 | 추후 추가 예정 |
