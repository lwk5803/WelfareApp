"""
address_api.py
--------------
카카오 로컬(Local) API의 주소 검색 기능을 이용해, 지번(구주소)이나 건물명으로
검색하면 정식 도로명주소 후보를 찾아주는 함수를 모아둔 파일입니다.

사용 전 준비:
    1. https://developers.kakao.com 접속 → 카카오 계정으로 로그인
    2. [내 애플리케이션] > [애플리케이션 추가하기] 로 앱을 하나 생성
    3. 생성된 앱 > [앱 키] 메뉴에서 "REST API 키" 값을 복사
       (정부 API와 달리 본인인증/승인 절차 없이 즉시 발급됩니다)
    4. .streamlit/secrets.toml 파일에 아래 줄을 추가:
           KAKAO_REST_API_KEY = "복사한 REST API 키"

주의:
    - 이 기능은 인터넷 연결이 반드시 필요합니다. 사내 폐쇄망 환경에서는
      이 기능을 쓸 수 없으니, 그런 경우엔 주소를 수동으로 입력하는 방식을
      그대로 유지해야 합니다.
    - 무료 사용량에 제한이 있을 수 있으니(호출량이 아주 많아지는 경우),
      실제 운영 전에 카카오 디벨로퍼스의 최신 정책을 한 번 확인해보세요.
"""

import requests
import streamlit as st

ADDRESS_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class AddressLookupError(Exception):
    """주소 검색 중 문제가 생겼을 때, 사용자에게 보여줄 친절한 메시지를 담는 예외입니다."""
    pass


def _get_api_key() -> str:
    # secrets.toml 파일 자체가 없으면 st.secrets.get()도 FileNotFoundError를 던집니다.
    # (파일이 없을 때는 "키가 없다"가 아니라 "파일이 없다"는 다른 종류의 에러가 나서,
    # 이것까지 같이 잡아줘야 합니다.)
    try:
        api_key = st.secrets.get("KAKAO_REST_API_KEY")
    except FileNotFoundError:
        api_key = None

    if not api_key:
        raise AddressLookupError(
            "주소 검색 API 키가 설정되지 않았습니다. .streamlit/secrets.toml에 "
            "KAKAO_REST_API_KEY를 추가해주세요."
        )
    return api_key


def _call_kakao(url: str, api_key: str, keyword: str) -> list[dict]:
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {"query": keyword, "size": 5}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
    except requests.RequestException as e:
        raise AddressLookupError(
            "주소 검색 서비스에 연결할 수 없습니다. 인터넷 연결을 확인해주세요."
        ) from e

    # 카카오 API는 키가 잘못됐거나 만료된 경우 401(인증 실패)을 돌려줍니다.
    if response.status_code == 401:
        raise AddressLookupError(
            "주소 검색 API 키가 유효하지 않습니다. secrets.toml의 KAKAO_REST_API_KEY를 확인해주세요."
        )
    # 403은 키 자체는 맞지만, 이 앱에서 "카카오맵" 상품이 아직 켜져 있지 않을 때 주로 발생합니다.
    if response.status_code == 403:
        raise AddressLookupError(
            "주소 검색 권한이 없습니다. 카카오 디벨로퍼스 > 앱 > 제품 설정 > 카카오맵에서 "
            "'사용 설정'이 켜져 있는지 확인해주세요."
        )
    if response.status_code != 200:
        raise AddressLookupError(f"주소 검색에 실패했습니다. (상태 코드: {response.status_code})")

    try:
        data = response.json()
    except ValueError as e:
        raise AddressLookupError("주소 검색 결과를 해석하지 못했습니다.") from e

    return data.get("documents", [])


def search_road_address(keyword: str) -> list[dict]:
    """
    지번(구주소), 건물명, 도로명 일부 등을 검색어로 넣으면,
    후보 주소 목록을 돌려줍니다.

    반환값 예시:
        [{"road_address": "서울 강남구 테헤란로 123",
          "jibun_address": "서울 강남구 역삼동 123-45",
          "zip_code": "06123"}, ...]

    카카오 API는 검색어가 도로명 주소로 매칭되지 않는 경우(예: 신축 건물,
    도로명이 아직 없는 지역 등) road_address 정보가 없을 수 있습니다.
    이런 경우 road_address는 빈 문자열로 채워집니다.

    검색 결과가 없으면 빈 리스트를 돌려줍니다 (에러가 아닙니다).
    API 키가 없거나, 네트워크 문제, API 자체 오류가 있으면 AddressLookupError를 던집니다.
    """
    api_key = _get_api_key()

    documents = _call_kakao(ADDRESS_SEARCH_URL, api_key, keyword)

    results = []
    for doc in documents:
        # road_address는 도로명 주소로 매칭이 안 되면 None일 수 있습니다.
        road_info = doc.get("road_address") or {}
        jibun_info = doc.get("address") or {}

        results.append({
            "road_address": road_info.get("address_name", ""),
            "jibun_address": jibun_info.get("address_name", "") or doc.get("address_name", ""),
            "zip_code": road_info.get("zone_no", ""),
            "place_name": "",
        })

    # 주소 검색 API는 정확한 지번/도로명 형식만 인식하고, 건물명·상호명(예: "행복빌라",
    # "OO경로당")으로는 검색이 안 됩니다. 결과가 없으면 건물명/장소명까지 찾아주는
    # 키워드 검색 API로 한 번 더 시도합니다. 이 API는 우편번호를 주지 않으므로
    # zip_code는 빈 문자열로 둡니다.
    if not results:
        documents = _call_kakao(KEYWORD_SEARCH_URL, api_key, keyword)
        for doc in documents:
            road_name = doc.get("road_address_name", "")
            jibun_name = doc.get("address_name", "")
            results.append({
                "road_address": road_name or jibun_name,
                "jibun_address": jibun_name,
                "zip_code": "",
                "place_name": doc.get("place_name", ""),
            })

    return results