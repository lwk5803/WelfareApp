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
       (Encoding된 키, Decoding된 키 둘 중 뭘 붙여넣어도 동작하도록,
        아래 코드에서 한 번 디코딩한 뒤 requests가 다시 인코딩하게 합니다.)

주의: 인터넷 연결이 필요합니다.
"""

import xml.etree.ElementTree as ET
from urllib.parse import unquote

import requests
import streamlit as st

LIST_URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"
DETAIL_URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfaredetailedV001"

# 코드표 (가구유형) - 활용가이드 문서 기준
TARGET_CODE_BY_WELFARE_TYPE = {
    "차상위": "050",  # 저소득
    "수급자": "050",  # 저소득
    # "일반"은 특정 가구유형에 해당하지 않으므로 필터를 걸지 않습니다.
}

# 에러코드 표 - 활용가이드 문서 기준
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

    # 공공데이터포털은 Encoding된 키와 Decoding된 키를 둘 다 제공합니다.
    # unquote()로 한 번 디코딩해두면, 어느 쪽을 붙여넣으셔도 requests가
    # 요청을 보낼 때 정확히 한 번만 인코딩하게 되어 안전합니다.
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
    if result_code and result_code != "0":
        friendly = ERROR_MESSAGES.get(result_code, _text(root, "resultMessage") or "알 수 없는 오류")
        raise GovWelfareError(f"공공데이터 API 오류({result_code}): {friendly}")

    return root


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
                  "일반"이거나 빈 값이면 이 조건은 사용하지 않습니다.
    search_word: 검색어 (제목+내용 기준으로 검색)

    반환값의 각 항목: servId, servNm, servDgst, lifeArray, trgterIndvdlArray,
                     intrsThemaArray, servDtlLink
    """
    api_key = _get_api_key()

    params = {
        "serviceKey": api_key,
        "callTp": "L",
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        # srchKeyCode는 필수 파라미터입니다. "003"은 제목+내용을 함께 검색합니다.
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


def fetch_welfare_detail(serv_id: str) -> dict:
    """
    특정 서비스(serv_id)의 상세 정보를 가져옵니다.
    반환값: servId, servNm, jurMnofNm(주관부처), outline(개요), target(지원대상),
            criteria(선정기준), benefit(지원내용), apply_methods(신청방법 안내 목록)
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