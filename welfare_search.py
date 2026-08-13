"""
welfare_search.py
------------------
Tavily 검색 API로 웹에서 정보를 찾아오는 함수들을 모아둔 파일입니다.
실제 검색어는 이제 이 파일이 아니라 GPT가 대화 중에 스스로 정해서
ai_recommend.py를 통해 search_web()을 직접 부르는 방식으로 동작합니다.

사용 전 준비:
    1. https://app.tavily.com 에서 회원가입 후 API 키 발급 (무료 사용량 제공)
    2. .streamlit/secrets.toml 파일에 아래 줄을 추가:
           TAVILY_API_KEY = "발급받은 키"

주의: 이 기능은 인터넷 연결이 반드시 필요합니다.
"""

import requests
import streamlit as st

API_URL = "https://api.tavily.com/search"

# 같은 검색어로 다시 검색할 때 API를 재호출하지 않도록 캐싱하는 유효기간(초 단위).
# 웹 검색 결과는 정부 공식 데이터보다는 자주 바뀔 수 있어서, gov_welfare_api.py의
# 24시간보다 짧은 12시간으로 뒀습니다.
CACHE_TTL_SECONDS = 60 * 60 * 12


class WelfareSearchError(Exception):
    """복지서비스 검색 중 문제가 생겼을 때, 사용자에게 보여줄 친절한 메시지를 담는 예외입니다."""
    pass


def _get_api_key() -> str:
    try:
        api_key = st.secrets.get("TAVILY_API_KEY")
    except FileNotFoundError:
        api_key = None

    if not api_key:
        raise WelfareSearchError(
            "복지서비스 검색 API 키가 설정되지 않았습니다. .streamlit/secrets.toml에 "
            "TAVILY_API_KEY를 추가해주세요."
        )
    return api_key


def extract_region(address: str) -> str:
    """
    주소 문자열에서 시/군/구 수준의 지역명만 뽑아냅니다 (상세 주소·건물명은 제외).
    예: "서울특별시 강남구 테헤란로 123" -> "서울특별시 강남구"
    """
    if not address:
        return ""
    parts = address.strip().split()
    return " ".join(parts[:2])


# 정부 API는 "서울특별시", "부산광역시"처럼 정식 행정구역명을 기준으로 지역을 매칭합니다.
# 실제 회원 주소는 "서울시", "부산시"처럼 일상적인 약칭으로 입력되는 경우가 흔해서,
# 이 약칭들을 정식 명칭으로 바꿔주지 않으면 API가 그 지역을 못 찾아 결과가 0건이 됩니다.
CTPV_NAME_ALIASES = {
    "서울시": "서울특별시",
    "부산시": "부산광역시",
    "대구시": "대구광역시",
    "인천시": "인천광역시",
    "광주시": "광주광역시",
    "대전시": "대전광역시",
    "울산시": "울산광역시",
    "세종시": "세종특별자치시",
    "경기": "경기도",
    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "충북": "충청북도",
    "충남": "충청남도",
    "전북": "전북특별자치도",
    "전라북도": "전북특별자치도",
    "전남": "전라남도",
    "경북": "경상북도",
    "경남": "경상남도",
    "제주": "제주특별자치도",
    "제주도": "제주특별자치도",
}


def normalize_ctpv_name(ctpv_nm: str) -> str:
    """시/도 약칭을 정부 API가 인식하는 정식 행정구역명으로 바꿔줍니다."""
    return CTPV_NAME_ALIASES.get(ctpv_nm, ctpv_nm)


def extract_ctpv_sgg(address: str) -> tuple[str, str]:
    """
    주소 문자열에서 시/도와 시/군/구를 따로 분리해서 돌려줍니다.
    지자체복지서비스 API가 이 둘을 별도의 파라미터(ctpvNm, sggNm)로 요구하기 때문입니다.
    시/도는 API가 인식하는 정식 명칭으로 자동 변환합니다.

    예: "서울특별시 강남구 테헤란로 123" -> ("서울특별시", "강남구")
        "부산시 해운대구 센텀중앙로 45" -> ("부산광역시", "해운대구")  <- 약칭 자동 변환
    """
    if not address:
        return "", ""
    parts = address.strip().split()
    ctpv_nm = normalize_ctpv_name(parts[0]) if len(parts) >= 1 else ""
    sgg_nm = parts[1] if len(parts) >= 2 else ""
    return ctpv_nm, sgg_nm


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    주어진 검색어로 웹을 검색합니다.
    반환값: [{"title": ..., "url": ..., "content": ...}, ...]
    """
    api_key = _get_api_key()

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=15)
    except requests.RequestException as e:
        raise WelfareSearchError(
            "검색 서비스에 연결할 수 없습니다. 인터넷 연결을 확인해주세요."
        ) from e

    if response.status_code == 401:
        raise WelfareSearchError(
            "검색 API 키가 유효하지 않습니다. secrets.toml의 TAVILY_API_KEY를 확인해주세요."
        )
    if response.status_code != 200:
        raise WelfareSearchError(f"검색에 실패했습니다. (상태 코드: {response.status_code})")

    try:
        data = response.json()
    except ValueError as e:
        raise WelfareSearchError("검색 결과를 해석하지 못했습니다.") from e

    results = data.get("results", []) or []
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
        }
        for item in results
    ]