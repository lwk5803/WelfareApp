"""
parsers.py
----------
사용자가 자유롭게 입력한 텍스트(생년월일, 전화번호)를,
저장하기 전에 정해진 형식으로 정규화(파싱)하는 함수들을 모아둔 파일입니다.

예: "900101" -> "1990-01-01"
    "01012345678" -> "010-1234-5678"

<<<<<<< HEAD
app.py나 database.py와 마찬가지로, "입력값을 다듬는 역할"만 따로 떼어내서
한 파일에 모아두면, 나중에 규칙이 바뀌어도 이 파일만 고치면 됩니다.
"""

import re


def parse_birth_date(raw: str) -> str:
=======
각 함수는 (정규화된 값, 인식에 성공했는지 여부) 형태의 튜플을 돌려줍니다.
인식에 실패하면 원본 문자열을 그대로 돌려주면서 False를 같이 알려주므로,
호출하는 쪽(app.py)에서 "이 값은 인식 못 했다"는 걸 사용자에게 알려줄 수 있습니다.
"""

import re
from datetime import datetime


def parse_birth_date(raw: str) -> tuple[str, bool]:
>>>>>>> 20ddd87a88015cdb6507b566a6429ff0d5c1784a
    """
    다양한 형식으로 입력된 생년월일을 "YYYY-MM-DD" 형식으로 정규화합니다.

    지원하는 입력 예시:
        "1990-01-01", "1990.1.1", "1990/1/1" -> 구분자가 있으면 월/일이 한 자리여도 정확히 인식
        "19900101" (8자리, 구분자 없음) -> "1990-01-01"
        "900101"   (6자리, 주민등록번호 앞자리 형식) -> "1990-01-01"

<<<<<<< HEAD
    인식할 수 없는 형식이면, 원본 문자열을 그대로 돌려줍니다.
    (담당자가 목록에서 육안으로 확인하고 다시 수정할 수 있도록)
=======
    반환값: (정규화된 문자열 또는 원본, 인식 성공 여부)
    형식은 맞아도 실제로 존재하지 않는 날짜("1990-13-99" 등)이거나,
    아예 인식할 수 없는 형식이면 (원본 문자열, False)를 돌려줍니다.
>>>>>>> 20ddd87a88015cdb6507b566a6429ff0d5c1784a
    """
    raw = raw.strip()

    # 1) 구분자(-, ., /, 공백)가 있는 경우를 먼저 확인합니다.
<<<<<<< HEAD
    #    이렇게 먼저 확인해야, "1990.1.1"처럼 월/일이 한 자리인 입력이
    #    숫자만 남겼을 때(199011, 6자리)와 헷갈리지 않습니다.
    match = re.match(r"^(\d{4})[.\-/\s]+(\d{1,2})[.\-/\s]+(\d{1,2})$", raw)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
=======
    match = re.match(r"^(\d{4})[.\-/\s]+(\d{1,2})[.\-/\s]+(\d{1,2})$", raw)
    if match:
        year, month, day = match.groups()
        candidate = f"{year}-{int(month):02d}-{int(day):02d}"
        if _is_valid_date(candidate):
            return candidate, True
        return raw, False
>>>>>>> 20ddd87a88015cdb6507b566a6429ff0d5c1784a

    # 2) 구분자가 없는 경우 - 순수 숫자 개수로 형식을 판단합니다.
    digits = re.sub(r"\D", "", raw)

    if len(digits) == 8:
<<<<<<< HEAD
        # 8자리: YYYYMMDD
        year, month, day = digits[:4], digits[4:6], digits[6:8]
    elif len(digits) == 6:
        # 6자리: YYMMDD (주민등록번호 앞자리와 같은 형식)
=======
        year, month, day = digits[:4], digits[4:6], digits[6:8]
    elif len(digits) == 6:
>>>>>>> 20ddd87a88015cdb6507b566a6429ff0d5c1784a
        # 주의: 이 프로그램은 노인복지관처럼 대상자 연령대가 높은 경우를 가정해
        #      2자리 연도를 전부 "19xx"년생으로 처리합니다.
        #      젊은 대상자가 많은 기관이라면 이 부분을 상황에 맞게 조정하세요.
        yy, month, day = digits[:2], digits[2:4], digits[4:6]
        year = "19" + yy
    else:
<<<<<<< HEAD
        # 인식할 수 없는 형식이면 원본 그대로 반환
        return raw

    return f"{year}-{month}-{day}"


def parse_phone(raw: str) -> str:
=======
        return raw, False

    candidate = f"{year}-{month}-{day}"
    if _is_valid_date(candidate):
        return candidate, True
    return raw, False


def _is_valid_date(candidate: str) -> bool:
    """"YYYY-MM-DD" 문자열이 실제 달력에 존재하는 날짜인지 확인합니다."""
    try:
        datetime.strptime(candidate, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def parse_phone(raw: str) -> tuple[str, bool]:
>>>>>>> 20ddd87a88015cdb6507b566a6429ff0d5c1784a
    """
    다양한 형식으로 입력된 전화번호를 "000-0000-0000" 형식으로 정규화합니다.

    지원하는 입력 예시:
        "01012345678"      (11자리, 휴대폰)      -> "010-1234-5678"
        "021234567"        (9자리, 서울 지역번호)  -> "02-123-4567"
        "0212345678"       (10자리, 서울 지역번호) -> "02-1234-5678"
        "0311234567"       (10자리, 일반 지역번호) -> "031-123-4567"

<<<<<<< HEAD
    인식할 수 없는 형식이면, 원본 문자열을 그대로 돌려줍니다.
=======
    반환값: (정규화된 문자열 또는 원본, 인식 성공 여부)
>>>>>>> 20ddd87a88015cdb6507b566a6429ff0d5c1784a
    """
    digits = re.sub(r"\D", "", raw)

    if len(digits) == 11:
<<<<<<< HEAD
        # 휴대폰 번호: 3-4-4
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    elif len(digits) == 10 and digits.startswith("02"):
        # 서울 지역번호: 2-4-4
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    elif len(digits) == 9 and digits.startswith("02"):
        # 서울 지역번호(구형, 짧은 국번): 2-3-4
        return f"{digits[:2]}-{digits[2:5]}-{digits[5:]}"
    elif len(digits) == 10:
        # 그 외 일반 지역번호/구형 휴대폰: 3-3-4
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    else:
        # 인식할 수 없는 형식이면 원본 그대로 반환
        return raw.strip()
=======
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}", True
    elif len(digits) == 10 and digits.startswith("02"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}", True
    elif len(digits) == 9 and digits.startswith("02"):
        return f"{digits[:2]}-{digits[2:5]}-{digits[5:]}", True
    elif len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}", True
    else:
        return raw.strip(), False
>>>>>>> 20ddd87a88015cdb6507b566a6429ff0d5c1784a
