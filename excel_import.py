"""
excel_import.py
----------------
기존에 쓰시던 회원 명단 엑셀 파일을 읽어서, 우리 시스템의 회원 스키마
(성명, 성별, 생년월일, 주소, 전화번호, 회원 구분, 비고)로 정리하는 함수들을 모아둔 파일입니다.

이 파일 자체는 화면(Streamlit)을 몰라도 되게, "엑셀 읽기"와 "한 행 정리하기"만 담당합니다.
실제로 업로드 UI를 그리고 db.add_client를 반복 호출하는 건 app_frontend.py가 합니다.
"""

import pandas as pd

import parsers

WELFARE_TYPE_CHOICES = ["일반", "차상위", "수급자"]


def read_excel_preview(file) -> pd.DataFrame:
    """업로드된 엑셀 파일을 pandas DataFrame으로 읽어옵니다."""
    return pd.read_excel(file)


def _clean(value) -> str:
    """
    엑셀 셀 값을 안전한 문자열로 바꿉니다. 빈 칸(NaN)은 빈 문자열로 처리합니다.

    주의: 엑셀은 "900101"처럼 숫자로만 이루어진 셀을 자동으로 숫자로 인식해버려서,
    pandas로 읽으면 900101.0 처럼 끝에 ".0"이 붙은 실수(float)로 들어옵니다.
    이 상태로 그냥 문자열로 바꾸면 "900101.0"이 되고, 여기서 "."을 제거하면
    끝자리에 가짜 "0"이 하나 더 남는(예: 전화번호 뒷자리가 틀어지는) 심각한 문제로
    이어집니다. 그래서 "정수값을 가진 실수"는 먼저 정수로 바꾼 뒤 문자열로 변환합니다.
    """
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_row(mapped_row: dict) -> tuple[dict, list[str]]:
    """
    엑셀 한 행에서 매핑된 값들(mapped_row)을 받아, DB에 저장할 수 있는 형태로 정리합니다.

    mapped_row 예시: {"name": "홍길동", "gender": "남", "birth_date": "900101", ...}
    (매칭 안 한 항목은 값이 None으로 들어옵니다.)

    반환값: (정리된 딕셔너리, 경고 메시지 리스트)
    """
    warnings = []

    name = _clean(mapped_row.get("name"))

    gender_raw = _clean(mapped_row.get("gender"))
    if gender_raw in ("남", "남성", "M", "m"):
        gender = "남"
    elif gender_raw in ("여", "여성", "F", "f"):
        gender = "여"
    elif gender_raw:
        gender = ""
        warnings.append(f"성별 '{gender_raw}'을(를) 인식하지 못해 비워뒀습니다.")
    else:
        gender = ""

    birth_raw = _clean(mapped_row.get("birth_date"))
    if birth_raw:
        birth_date, birth_ok = parsers.parse_birth_date(birth_raw)
        if not birth_ok:
            warnings.append(f"생년월일 '{birth_raw}'을(를) 인식하지 못해 원본 그대로 저장합니다.")
    else:
        birth_date = ""

    phone_raw = _clean(mapped_row.get("phone"))
    if phone_raw:
        phone, phone_ok = parsers.parse_phone(phone_raw)
        if not phone_ok:
            warnings.append(f"전화번호 '{phone_raw}'을(를) 인식하지 못해 원본 그대로 저장합니다.")
    else:
        phone = ""

    address = _clean(mapped_row.get("address"))

    welfare_type_raw = _clean(mapped_row.get("welfare_type"))
    if welfare_type_raw in WELFARE_TYPE_CHOICES:
        welfare_type = welfare_type_raw
    elif welfare_type_raw:
        welfare_type = "일반"
        warnings.append(f"회원 구분 '{welfare_type_raw}'을(를) 인식하지 못해 '일반'으로 저장합니다.")
    else:
        welfare_type = "일반"

    note = _clean(mapped_row.get("note"))

    normalized = {
        "name": name,
        "gender": gender,
        "birth_date": birth_date,
        "address": address,
        "phone": phone,
        "welfare_type": welfare_type,
        "note": note,
    }
    return normalized, warnings