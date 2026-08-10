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