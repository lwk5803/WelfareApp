# WelfareApp

복지관 회원 관리 시스템입니다. 회원 등록/수정/삭제, 엑셀 일괄등록, 통계, 그리고
정부 복지 데이터(중앙부처+지자체) 조회와 LLM을 결합한 맞춤 복지서비스 추천 기능을
제공합니다.

## 아키텍처

FastAPI(백엔드 + 화면) ↔ Supabase(Postgres) 구조로 동작합니다. 예전에는 Streamlit으로
화면을 따로 띄웠는데, 지금은 FastAPI 하나가 API와 화면(Jinja2 템플릿)을 모두 담당합니다.

- `main.py` — FastAPI. 회원 CRUD, 통계, 주소 검색, AI 추천 API + 화면 라우트를 모두 제공합니다.
- `templates/` — 화면(Jinja2 HTML), `static/` — CSS/JS.
- `supabase_db.py` — Supabase(Postgres) 저장/조회.

## 설치

```bash
pip install -r requirements.txt
```

## 실행

서버 하나만 켜면 됩니다.

```bash
uvicorn main:app --reload --port 8000
```

브라우저에서 `http://localhost:8000` 접속하면 됩니다.

## Supabase 설정

Supabase 프로젝트에서 SQL Editor로 아래를 실행해 `clients` 테이블을 만드세요.

```sql
create table if not exists clients (
    id bigint generated always as identity primary key,
    name text not null,
    gender text,
    birth_date text,
    address text,
    phone text,
    welfare_type text,
    note text,
    created_at timestamptz not null default now(),
    consent_personal text,
    consent_sensitive text,
    consent_third_party text,
    consent_portrait text,
    consent_signed_at timestamptz
);

alter table clients enable row level security;

create unique index if not exists idx_clients_phone_unique
    on clients (phone)
    where phone is not null and phone <> '';
```

그다음 `sql/` 폴더의 마이그레이션을 파일명 순서(001→009)대로 SQL Editor에서 차례로
실행하세요. 로그인/권한(`profiles` 테이블), 회원번호 자동부여, 소프트 삭제, 사진/서명
저장, 가구유형/장애/질병/경력 등 세부 항목, 정보 갱신일(`updated_at`)까지 여기서
전부 채워집니다. 로그인 계정은 Supabase Authentication > Users에서 만들고, 관리자로
지정하려면 SQL Editor에서 아래처럼 실행하세요.

```sql
update profiles set role = 'admin' where email = '담당자 이메일';
```

## API 키 설정

프로젝트 루트에 `.env` 파일을 만들고 아래 값을 채워주세요
(이 파일은 git에 커밋되지 않습니다).

```env
SUPABASE_URL=...           # Supabase 프로젝트 URL
SUPABASE_SECRET_KEY=...    # Supabase service_role 키 (백엔드 전용, 절대 프론트에 노출 금지)
SUPABASE_JWKS_URL=...      # Supabase Auth JWKS URL (로그인 토큰 검증용)

KAKAO_REST_API_KEY=...     # 주소 검색 (address_api.py)
TAVILY_API_KEY=...         # 복지 정보 웹 검색 (welfare_search.py)
GOV_WELFARE_API_KEY=...    # 정부 복지 서비스 API - 중앙부처/지자체 (gov_welfare_api.py)

OPENAI_API_KEY=...         # 추천 복지 서비스 - gpt-4o-mini (유료)
AI_PROVIDER=openai         # "openai"(gpt-4o-mini, 유료) 또는 "local"(Ollama, 무료)
```

`AI_PROVIDER = "local"`로 두면 비용 없이 로컬 모델(기본값 Ollama `gemma4`)로 테스트할 수
있습니다. 이 경우 미리 `ollama serve`로 Ollama를 켜두고 `ollama pull gemma4`로 모델을
받아두세요.

키가 없어도 앱은 실행되며, 해당 기능을 사용할 때만 안내 메시지가 표시됩니다.

## AI 복지서비스 추천

회원 프로필(나이·성별·회원구분·거주지역·비고)을 바탕으로, 정부 공공데이터(중앙부처 +
거주 지자체)와 웹 검색을 함께 활용해 맞춤 서비스를 정리해줍니다.

- 성별·생애주기가 명백히 안 맞는 서비스는 코드 단계에서 먼저 제외합니다.
- 장애인·국가유공자 등 프로필에 없는 특수 자격이 필요한 서비스는 "회원님께 맞는
  복지서비스"에 넣지 않고 "참고: 조건부 서비스"로 따로 정리합니다.
- 비고(예: "조손가정", "독거노인")는 검색 키워드로도 함께 활용됩니다.
- 각 추천 서비스에는 실제 출처 링크(복지로 등)를 표시합니다.

## 프로젝트 구조

| 파일 | 역할 |
| --- | --- |
| `main.py` | FastAPI (회원 CRUD, 통계, 추천 API + 화면 라우트) |
| `templates/` | 화면 (Jinja2 HTML) |
| `static/` | CSS/JS (서명 캔버스, 통계 차트 등) |
| `auth.py` | 로그인/권한 (Supabase Auth, JWT 검증) |
| `config.py` | .env에서 API 키 등 시크릿을 읽는 모듈 |
| `supabase_db.py` | Supabase 저장/조회 |
| `document.py` | 회원 등록 서류(.docx) 생성 |
| `parsers.py` | 입력값 정리 |
| `stats.py` | 회원 통계 계산 |
| `address_api.py` | 카카오 주소 검색 연동 |
| `excel_import.py` | 엑셀 일괄등록용 파싱 |
| `welfare_search.py` | 복지 정보 웹 검색 (Tavily) |
| `ai_recommend.py` | LLM 기반 복지 서비스 추천 (OpenAI/로컬 Ollama 선택 가능) |
| `gov_welfare_api.py` | 정부 복지 서비스 API 연동 (중앙부처+지자체), 성별/생애주기 필터링 |
| `ttl_cache.py` | 자주 안 바뀌는 API 응답을 잠깐 캐싱하는 TTL 캐시 |
| `sql/` | Supabase 마이그레이션 (파일명 순서대로 실행) |
| `docs/DEV_LOG.md` | 날짜별 변경 이력 (비전공자용 설명 포함) |
