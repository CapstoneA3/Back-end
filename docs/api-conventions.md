# API 설계 규칙

## 기본 원칙

- RESTful 설계
- 모든 엔드포인트 prefix: `/api/v1`
- 인증 방식: 미정 (구현 시 이 문서 업데이트 예정)
- 리소스는 복수형 명사: `/ingredients`, `/recipes`, `/inventory`
- 액션이 필요한 경우 동사 suffix 허용: `/recipes/{id}/complete`

---

## 응답 형식

모든 응답은 아래 구조를 따름.

### 성공
```json
{
  "success": true,
  "data": { },
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

---

## HTTP 상태 코드

| 코드 | 의미 |
|------|------|
| 200 | 성공 |
| 201 | 생성 성공 |
| 400 | 잘못된 요청 |
| 404 | 리소스 없음 |
| 500 | 서버 오류 |

---

## 주요 엔드포인트

### 식재료 마스터

| 메서드 | 경로 | 설명 | 기능 |
|--------|------|------|------|
| GET | `/api/v1/ingredients` | 식재료 검색/조회 | ingredient_master 조회 |
| GET | `/api/v1/ingredients/{id}` | 식재료 단건 조회 | |

### 재고 (user_inventory)

| 메서드 | 경로 | 설명 | 기능 |
|--------|------|------|------|
| GET | `/api/v1/inventory` | 내 재고 목록 | 신호등 분류 + 정렬 포함 (F-02) |
| POST | `/api/v1/inventory` | 재료 등록 | BitSet 갱신 포함 (F-01) |
| PATCH | `/api/v1/inventory/{id}` | 재고 수정 | 수량·유통기한 수정 (F-05) |
| DELETE | `/api/v1/inventory/{id}` | 재고 삭제 | BitSet 갱신 포함 (F-05) |

### 레시피

| 메서드 | 경로 | 설명 | 기능 |
|--------|------|------|------|
| GET | `/api/v1/recipes` | 추천 레시피 목록 | 비트마스킹 + α-스코어 (F-03) |
| GET | `/api/v1/recipes/{id}` | 레시피 상세 조회 | |
| POST | `/api/v1/recipes/{id}/complete` | 요리 완료 처리 | FIFO 차감 + BitSet 갱신 (F-04) |

---

## 쿼리 파라미터 규칙

- 정렬: `?sort=recommended` 또는 `?sort=expire_date`
- 페이지네이션: `?page=1&size=20` (필요 시 적용)
- 검색: `?q=검색어`
