# WelfareApp

복지관 회원 관리를 위한 Streamlit 웹 앱입니다. 회원 등록/수정/삭제, 통계, 추천 복지 서비스 조회 기능을 제공합니다.

## 설치

```bash
pip install -r requirements.txt
```

## 실행

```bash
streamlit run app.py
```

첫 실행 시 `database.py`가 SQLite 데이터베이스(`welfare.db`)를 자동으로 생성합니다.

## API 키 설정

일부 기능은 외부 API 키가 필요합니다. 프로젝트 루트에 `.streamlit/secrets.toml` 파일을 만들고 아래 값을 채워주세요 (이 파일은 git에 커밋되지 않습니다).

```toml
OPENAI_API_KEY = "..."        # 추천 복지 서비스 (ai_recommend.py)
GOV_WELFARE_API_KEY = "..."   # 정부 복지 서비스 조회 (gov_welfare_api.py)
KAKAO_REST_API_KEY = "..."    # 주소 검색 (address_api.py)
TAVILY_API_KEY = "..."        # 복지 정보 검색 (welfare_search.py)
```

키가 없어도 앱은 실행되며, 해당 기능을 사용할 때만 안내 메시지가 표시됩니다.

## 프로젝트 구조

| 파일 | 역할 |
| --- | --- |
| `app.py` | Streamlit 화면 구성 |
| `database.py` | SQLite 저장/조회 |
| `parsers.py` | 입력값 정리 |
| `stats.py` | 회원 통계 계산 |
| `address_api.py` | 카카오 주소 검색 연동 |
| `excel_import.py` | 엑셀 가져오기 |
| `welfare_search.py` | 복지 정보 검색 (Tavily) |
| `ai_recommend.py` | AI 기반 복지 서비스 추천 |
| `gov_welfare_api.py` | 정부 복지 서비스 API 연동 |
