"""
gov_welfare_api.py
--------------------
공공데이터포털(data.go.kr)의 "한국사회보장정보원_중앙부처복지서비스" API로,
정부의 공식 복지서비스 목록/상세 정보를 가져오는 함수들을 모아둔 파일입니다.

이 파일의 요청 파라미터는 공식 활용가이드 문서(활용가이드_중앙부처복지서비스_v2.2)를
그대로 따랐습니다.

사용 전 준비:
    1. https://www.data.go.kr 에서 "한국사회보장정보원_중앙부처복지서비스" 활용신청
       (보통 자동승인) 후 인증키 발급
    2. .streamlit/secrets.toml에 아래 줄 추가:
           GOV_WELFARE_API_KEY = "발급받은 인증키"

주의: 인터넷 연결이 필요합니다.
"""

import xml.etree.ElementTree as ET
from urllib.parse import unquote

import requests
import streamlit as st

LIST_URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"
DETAIL_URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfaredetailedV001"

# 지자체(시/도, 시/군/구) 복지서비스 API - 같은 제공기관(한국사회보장정보원)의 별도 데이터셋
LOCAL_LIST_URL = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations/LcgvWelfarelist"
LOCAL_DETAIL_URL = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations/LcgvWelfaredetailed"

# 같은 조건으로 반복 조회할 때 API를 다시 호출하지 않도록 캐싱하는 유효기간(초 단위).
# 정부 복지 정보가 하루 만에 자주 바뀌진 않으니 24시간으로 뒀습니다.
CACHE_TTL_SECONDS = 60 * 60 * 24

TARGET_CODE_BY_WELFARE_TYPE = {
    "차상위": "050",  # 저소득
    "수급자": "050",  # 저소득
}

ERROR_MESSAGES = {
    "04": "HTTP 오류가 발생했습니다.",
    "10": "요청 파라미터가 잘못되었습니다.",
    "12": "해당 오픈API 서비스가 없거나 폐기되었습니다.",
    "20": "서비스 접근이 거부되었습니다.",
    "22": "서비스 요청 제한 횟수를 초과했습니다. 잠시 후 다시 시도해주세요.",
    "30": "등록되지 않은 서비스키입니다. secrets.toml의 GOV_WELFARE_API_KEY를 확인해주세요.",
    "31": "API 활용기간이 만료되었습니다.",
    "99": "알 수 없는 오류가 발생했습니다.",
}

# 이 코드들은 "진짜 에러"가 아니라 "조회 조건에 맞는 결과가 없다"는 뜻으로 쓰입니다.
# (중앙부처복지서비스 API는 결과가 없을 때도 그냥 resultCode "0" + 빈 목록으로 응답하는데,
#  지자체복지서비스 API는 이 상황을 "40"번으로 따로 알려줍니다. 같은 제공기관이어도
#  데이터셋마다 이런 세부 규칙이 다를 수 있다는 걸 실제로 겪고 나서 추가했습니다.)
NO_RESULT_CODES = {"40"}


class GovWelfareError(Exception):
    """공공데이터 복지서비스 API 호출 중 문제가 생겼을 때, 보여줄 친절한 메시지를 담는 예외입니다."""
    pass


def _get_api_key() -> str:
    try:
        raw_key = st.secrets.get("GOV_WELFARE_API_KEY")
    except FileNotFoundError:
        raw_key = None

    if not raw_key:
        raise GovWelfareError(
            "공공데이터 복지서비스 API 키가 설정되지 않았습니다. .streamlit/secrets.toml에 "
            "GOV_WELFARE_API_KEY를 추가해주세요."
        )
    return unquote(raw_key)


def _text(elem, tag: str) -> str:
    """elem 아래의 tag를 찾아 텍스트를 돌려줍니다. 없으면 빈 문자열을 돌려줍니다."""
    found = elem.find(tag)
    return found.text.strip() if (found is not None and found.text) else ""


def _request_xml(url: str, params: dict) -> ET.Element:
    """공통 요청 처리: GET 요청 → XML 파싱 → resultCode 확인까지 한 번에 처리합니다."""
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        raise GovWelfareError("공공데이터 API에 연결할 수 없습니다. 인터넷 연결을 확인해주세요.") from e

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as e:
        raise GovWelfareError("공공데이터 API 응답(XML)을 해석하지 못했습니다. 인증키를 확인해주세요.") from e

    result_code = _text(root, "resultCode")

    if result_code in NO_RESULT_CODES:
        # 결과가 없을 뿐 진짜 에러는 아니므로, 예외를 던지지 않고 그대로 돌려줍니다.
        # 이 응답에는 <servList>/<applmetList> 같은 태그가 원래 없으므로,
        # 뒤에서 root.findall(...)을 해도 자연스럽게 빈 리스트가 됩니다.
        return root

    if result_code and result_code != "0":
        friendly = ERROR_MESSAGES.get(result_code, _text(root, "resultMessage") or "알 수 없는 오류")
        raise GovWelfareError(f"공공데이터 API 오류({result_code}): {friendly}")

    return root


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_welfare_list(
    age: int | None = None,
    welfare_type: str | None = None,
    search_word: str | None = None,
    page_no: int = 1,
    num_of_rows: int = 20,
) -> list[dict]:
    """
    정부(중앙부처) 복지서비스 목록을 조회합니다.

    age: 나이를 직접 넘기면, 그 나이에 맞는 서비스로 서버가 걸러줍니다.
    welfare_type: "차상위"/"수급자"이면 가구유형(저소득) 코드로 필터링합니다.
    search_word: 검색어 (제목+내용 기준으로 검색)
    """
    api_key = _get_api_key()

    params = {
        "serviceKey": api_key,
        "callTp": "L",
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "srchKeyCode": "003",
    }

    if search_word:
        params["searchWrd"] = search_word
    if age is not None:
        params["age"] = age

    target_code = TARGET_CODE_BY_WELFARE_TYPE.get(welfare_type or "")
    if target_code:
        params["trgterIndvdlArray"] = target_code

    root = _request_xml(LIST_URL, params)

    services = []
    for item in root.findall("servList"):
        services.append({
            "servId": _text(item, "servId"),
            "servNm": _text(item, "servNm"),
            "servDgst": _text(item, "servDgst"),
            "lifeArray": _text(item, "lifeArray"),
            "trgterIndvdlArray": _text(item, "trgterIndvdlArray"),
            "intrsThemaArray": _text(item, "intrsThemaArray"),
            "servDtlLink": _text(item, "servDtlLink"),
        })
    return services


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_welfare_detail(serv_id: str) -> dict:
    """
    특정 서비스(serv_id)의 상세 정보를 가져옵니다.
    """
    api_key = _get_api_key()
    params = {
        "serviceKey": api_key,
        "callTp": "D",
        "servId": serv_id,
    }
    root = _request_xml(DETAIL_URL, params)

    apply_methods = []
    for item in root.findall("applmetList"):
        name = _text(item, "servSeDetailNm")
        link = _text(item, "servSeDetailLink")
        if name or link:
            apply_methods.append(f"{name}: {link}" if name else link)

    return {
        "servId": _text(root, "servId"),
        "servNm": _text(root, "servNm"),
        "jurMnofNm": _text(root, "jurMnofNm"),
        "outline": _text(root, "wlfareInfoOutlCn"),
        "target": _text(root, "tgtrDtlCn"),
        "criteria": _text(root, "slctCritCn"),
        "benefit": _text(root, "alwServCn"),
        "apply_methods": apply_methods,
    }


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_local_welfare_list(
    ctpv_nm: str | None = None,
    sgg_nm: str | None = None,
    age: int | None = None,
    welfare_type: str | None = None,
    search_word: str | None = None,
    page_no: int = 1,
    num_of_rows: int = 20,
) -> list[dict]:
    """
    지자체(시/도, 시/군/구) 복지서비스 목록을 조회합니다.

    ctpv_nm: 시/도명 (예: "서울특별시")
    sgg_nm: 시/군/구명 (예: "송파구") - 코드가 아니라 실제 지역명 텍스트를 그대로 넘깁니다.
    age: 나이를 직접 넘기면, 그 나이에 맞는 서비스로 서버가 걸러줍니다.
    welfare_type: "차상위"/"수급자"이면 가구상황(저소득) 코드로 필터링합니다.

    주의: 이 API는 중앙부처복지서비스 API와 달리 callTp 파라미터가 없습니다
    (목록조회/상세조회가 처음부터 서로 다른 주소로 나뉘어 있기 때문입니다).
    """
    api_key = _get_api_key()

    params = {
        "serviceKey": api_key,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "srchKeyCode": "003",
    }

    if ctpv_nm:
        params["ctpvNm"] = ctpv_nm
    if sgg_nm:
        params["sggNm"] = sgg_nm
    if search_word:
        params["searchWrd"] = search_word
    if age is not None:
        params["age"] = age

    target_code = TARGET_CODE_BY_WELFARE_TYPE.get(welfare_type or "")
    if target_code:
        params["trgterIndvdlArray"] = target_code

    root = _request_xml(LOCAL_LIST_URL, params)

    services = []
    for item in root.findall("servList"):
        services.append({
            "servId": _text(item, "servId"),
            "servNm": _text(item, "servNm"),
            "servDgst": _text(item, "servDgst"),
            "lifeArray": _text(item, "lifeArray"),
            "trgterIndvdlArray": _text(item, "trgterIndvdlArray"),
            "intrsThemaArray": _text(item, "intrsThemaArray"),
            "servDtlLink": _text(item, "servDtlLink"),
            # 지자체 서비스이니, 어느 지역 서비스인지 응답에도 있을 것으로 보고 같이 추출합니다.
            # 이 태그가 실제로 없어도 _text()가 빈 문자열을 돌려줄 뿐 에러는 안 납니다.
            "ctpvNm": _text(item, "ctpvNm"),
            "sggNm": _text(item, "sggNm"),
        })
    return services


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_local_welfare_detail(serv_id: str) -> dict:
    """
    특정 지자체 서비스(serv_id)의 상세 정보를 가져옵니다.

    주의: 이 API의 상세조회 응답 필드명은 활용가이드 문서로 확인하지 못해서,
    중앙부처복지서비스 API와 같은 제공기관(한국사회보장정보원)이 같은 복지로 데이터를
    쓴다는 점에 근거해 동일한 필드명(tgtrDtlCn, slctCritCn 등)을 그대로 사용했습니다.
    실제 응답과 다르면 _text()가 빈 문자열을 돌려줄 뿐 에러는 안 나지만, 내용이
    비어있는 채로 나온다면 이 부분을 실제 응답 기준으로 다시 확인해야 합니다.
    """
    api_key = _get_api_key()
    params = {
        "serviceKey": api_key,
        "servId": serv_id,
    }
    root = _request_xml(LOCAL_DETAIL_URL, params)

    apply_methods = []
    for item in root.findall("applmetList"):
        name = _text(item, "servSeDetailNm")
        link = _text(item, "servSeDetailLink")
        if name or link:
            apply_methods.append(f"{name}: {link}" if name else link)

    return {
        "servId": _text(root, "servId"),
        "servNm": _text(root, "servNm"),
        "jurMnofNm": _text(root, "jurMnofNm"),
        "outline": _text(root, "wlfareInfoOutlCn"),
        "target": _text(root, "tgtrDtlCn"),
        "criteria": _text(root, "slctCritCn"),
        "benefit": _text(root, "alwServCn"),
        "apply_methods": apply_methods,
    }