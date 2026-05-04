# 핵심 알고리즘 명세

## 1. BitSet 구조

`ingredient_master.bit_id` (0~426) 가 각 식재료의 비트 인덱스.  
사용자가 해당 재료를 보유하면 그 위치의 비트를 1로 세팅하여 Redis에 캐싱.

```
예) bit_id=0 (쌀) 보유, bit_id=2 (계란) 보유, bit_id=5 (우유) 미보유
→ ...001 0101  (이진수)
```

---

## 2. 비트마스킹 레시피 매칭

### 개요
각 레시피는 필요 재료의 bit_id 집합으로 구성된 `requirement_mask`를 보유.  
사용자 BitSet과 AND 연산으로 조리 가능 여부를 O(1)에 판단. 전체 레시피 순회는 O(n).

### 매칭 조건
```python
(user_bitset & recipe_mask) == recipe_mask
```

### requirement_mask 생성 방법
```python
mask = 0
for ingredient in recipe.ingredients:
    mask |= (1 << ingredient.bit_id)
```

### 처리 흐름
```
Redis에서 user_bitset 로드
→ 전체 레시피 순회
→ (user_bitset AND recipe_mask) == recipe_mask 인 레시피 추출
→ α-스코어링으로 정렬
```

---

## 3. α-스코어링 기반 레시피 우선순위 정렬

### 목적
조리 가능한 레시피 중 폐기 위험이 높은 재료를 가장 먼저 소비할 수 있는 레시피를 상위에 노출.

### 재료별 스코어 공식

```
score_ingredient = α × quantity / (D-day)² + 1

- α       : ingredient_master.risk_factor (0.1 / 1 / 2 / 3)
- quantity : user_inventory에서 해당 재료 보유 수량
- D-day   : expire_date - 오늘 날짜 (일 단위, 최솟값 1로 클리핑)
```

### 레시피 스코어 합산

```
score_recipe = Σ score_ingredient  (레시피에 포함된 보유 재료 전체)
```

레시피 스코어 내림차순 정렬 후 랭킹 반환.

### 예시
- 닭가슴살 (α=3, quantity=200g, D-day=1) → 3 × 200 / (1²+1) = 300
- 양파     (α=1, quantity=100g, D-day=5) → 1 × 100 / (5²+1) = 3.8
- 레시피 스코어 = 303.8

---

## 4. FIFO 재고 차감

### 트리거
사용자가 '요리 완료' 버튼 클릭.

### 처리 순서
1. 레시피의 `recipe_ingredient` 목록 조회
2. 각 재료별로 `user_inventory`에서 `expire_date` 오름차순 정렬 (선입선출)
3. 필요 수량만큼 순서대로 차감; 항목 수량이 0이 되면 해당 row 삭제
4. 재고가 완전히 소진된 재료 → Redis BitSet의 해당 `bit_id`를 0으로 전환 (Bit-Flip)

### 사용자 수량 수정
요리 완료 시 실제 사용량을 수정할 수 있음. 수정된 수량 기준으로 FIFO 차감 수행.

### Bit-Flip 조건
```python
remaining = sum(user_inventory 중 해당 ingredient_master_id의 quantity)
if remaining == 0:
    user_bitset &= ~(1 << bit_id)  # 해당 비트 OFF
    Redis에 갱신
```

---

## 5. 신호등 분류 기준 (대시보드)

재고 항목을 D-day와 risk_factor 기반으로 3단계로 시각 분류.

| 색상 | 의미 | 분류 기준 |
|------|------|-----------|
| 빨강 | 즉시 소진 요망 | 미확정 |
| 노랑 | 주의 | 미확정 |
| 초록 | 안전 | 미확정 |

> 임계값(D-day 기준) 및 risk_factor 반영 방식은 팀 내 확정 후 업데이트 예정
