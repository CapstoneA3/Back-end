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
