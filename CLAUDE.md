# 냉장고 재고 관리 & 레시피 추천 서비스 — 백엔드

## 프로젝트 개요

개인 냉장고의 식재료를 관리하고, 보유 재료 기반으로 최적 레시피를 추천하는 FastAPI 백엔드 서버.

### 해결하는 핵심 문제
1. **데이터 불일치**: 수동 입력 번거로움으로 발생하는 실제 재고와 앱 데이터 간의 차이
2. **LLM 한계**: 레시피 AI의 느린 응답·비현실적 결과·높은 운영 비용 → 비트마스킹으로 대체
3. **관리 효율성**: 유통기한 임박 식재료 우선 소진 유도

## 기술 스택

| 항목 | 기술 | 비고 |
|------|------|------|
| 웹 프레임워크 | FastAPI (Python 3.11+) | |
| 마스터/레시피 DB | Supabase (PostgreSQL) | ingredient_master 등 구현 완료 |
| 사용자 재고 DB | Supabase 또는 별도 서버 | 미확정, 구현 예정 |
| BitSet 캐시 | Redis | 레시피 매칭 고속화 |
| 인증 | 미정 | Supabase Auth 또는 JWT 예정 |

## 프로젝트 디렉토리 구조

```
app/
  routers/        # 엔드포인트별 라우터 (ingredients, inventory, recipes)
  services/       # 비즈니스 로직 (bitset, scoring, fifo 등)
  models/         # DB 모델
  schemas/        # Pydantic 요청/응답 스키마
  core/           # 설정, DB/Redis 연결
docs/             # 컨텍스트 문서 (이 폴더)
main.py
```

## 개발 규칙

- 언어: Python 3.11+, 코드 스타일 PEP8
- 모든 API 응답은 `docs/api-conventions.md`의 통일된 JSON 구조를 따름
- 비즈니스 로직은 `services/`에, 라우터는 얇게 유지
- Redis BitSet 변경은 항상 DB 변경과 함께 원자적으로 처리

## 문서 인덱스

| 문서 | 내용 |
|------|------|
| `docs/schema.md` | DB 테이블 스키마 전체 |
| `docs/algorithms.md` | 비트마스킹, α-스코어링, FIFO 알고리즘 명세 |
| `docs/features.md` | 기능 목록 및 구현 우선순위 |
| `docs/api-conventions.md` | API 설계 규칙 및 엔드포인트 목록 |
