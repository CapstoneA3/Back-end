# 데이터베이스 스키마

## Supabase (PostgreSQL) — 마스터/레시피 데이터

### ingredient_master (구현 완료)

식재료 기준 정보. 427개 항목, 11개 카테고리.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | int8 | PK |
| bit_id | int | BitSet 인덱스 (0~426) |
| name | varchar | 식재료명 |
| category | varchar | 카테고리 (`곡류/면/떡`, `육류`, `생선/해산물`, `채소`, `계란/콩/두부`, `유제품/치즈`, `김치/절임/묵`, `해조류/건어물`, `과일/견과`, `가공식품/기타`, `조미료`) |
| default_shelf_days | int4 | 표준 유통기한 (일) |
| risk_factor | numeric | 위험가중치 α (0.1 / 1 / 2 / 3) |

**위험가중치(α) 기준 (FDA 근거)**

| α | 카테고리 | 예시 |
|---|----------|------|
| 3 | 육류·어패류·유제품 | 고기, 생선, 우유 |
| 2 | 고수분·가열 식품 | 딸기, 두부, 베이컨 |
| 1 | 장기 보관 가능 농산물 | 감자, 양파, 사과 |
| 0.1 | 저수분·건조 가공식품 | 쌀, 파스타면, 조미료 |

---

### recipe (구현 예정)

레시피 기본 정보.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | - | PK |
| name | - | 레시피명 |
| description | - | 설명 |
| requirement_mask | - | 필요 재료 비트마스크 (docs/algorithms.md 참고) |

> 상세 컬럼은 구현 시 확정 후 업데이트 예정

---

### recipe_ingredient (구현 중)

레시피별 필요 재료 및 수량. 중량/단위 일부 항목 정리 중.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | int8 | PK |
| recipe_id | int8 | FK → recipe.id |
| ingredient_master_id | varchar | FK → ingredient_master.id |
| quantity | varchar | 필요 수량 |
| unit | varchar | 단위 |
| ingredient_name | text | 식재료명 (비정규화 보조 컬럼) |

---

### recipe_step (구현 예정)

레시피 조리 순서.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | - | PK |
| recipe_id | - | FK → recipe.id |
| step_order | - | 단계 순서 |
| description | - | 조리 설명 |

> 상세 컬럼은 구현 시 확정 후 업데이트 예정

---

## 사용자 재고 DB (미구현 — Supabase 또는 별도 서버 미확정)

### users (계획)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | - | PK |
| ... | - | 인증 방식 미확정, 상세 TBD |

---

### user_inventory (계획)

사용자가 실제 보유한 재료 인스턴스. FIFO 차감의 단위.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | - | PK |
| user_id | - | FK → users.id |
| ingredient_master_id | - | FK → ingredient_master.id |
| quantity | - | 보유 수량 |
| unit | - | 단위 |
| expire_date | date | 유통기한 (default_shelf_days 기반 자동 계산) |
| created_at | timestamp | 등록 시각 (FIFO 기준) |

---

## Redis — BitSet 캐시

사용자 보유 재료를 비트 배열로 캐싱하여 레시피 매칭에 활용.

| 항목 | 내용 |
|------|------|
| Key | `user:{user_id}:bitset` |
| Value | 427비트 정수 (bit_id 위치가 1이면 해당 재료 보유) |
| 갱신 시점 | 재료 추가 / 재료 삭제 / 요리 완료 시 |

> 알고리즘 상세는 `docs/algorithms.md` 참고
