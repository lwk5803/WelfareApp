"""
parsers.py
----------
사용자가 자유롭게 입력한 텍스트(생년월일, 전화번호)를,
저장하기 전에 정해진 형식으로 정규화(파싱)하는 함수들을 모아둔 파일입니다.

예: "900101" -> "1990-01-01"
    "01012345678" -> "010-1234-5678"

각 함수는 (정규화된 값, 인식에 성공했는지 여부) 형태의 튜플을 돌려줍니다.
인식에 실패하면 원본 문자열을 그대로 돌려주면서 False를 같이 알려주므로,
호출하는 쪽(main.py)에서 "이 값은 인식 못 했다"는 걸 사용자에게 알려줄 수 있습니다.
"""

import re
from datetime import datetime


def parse_birth_date(raw: str) -> tuple[str, bool]:
    """
    다양한 형식으로 입력된 생년월일을 "YYYY-MM-DD" 형식으로 정규화합니다.

    지원하는 입력 예시:
        "1990-01-01", "1990.1.1", "1990/1/1" -> 구분자가 있으면 월/일이 한 자리여도 정확히 인식
        "19900101" (8자리, 구분자 없음) -> "1990-01-01"
        "900101"   (6자리, 주민등록번호 앞자리 형식) -> "1990-01-01"

    반환값: (정규화된 문자열 또는 원본, 인식 성공 여부)
    형식은 맞아도 실제로 존재하지 않는 날짜("1990-13-99" 등)이거나,
    아예 인식할 수 없는 형식이면 (원본 문자열, False)를 돌려줍니다.
    """
    raw = raw.strip()

    # 1) 구분자(-, ., /, 공백)가 있는 경우를 먼저 확인합니다.
    match = re.match(r"^(\d{4})[.\-/\s]+(\d{1,2})[.\-/\s]+(\d{1,2})$", raw)
    if match:
        year, month, day = match.groups()
        candidate = f"{year}-{int(month):02d}-{int(day):02d}"
        if _is_valid_date(candidate):
            return candidate, True
        return raw, False

    # 1-1) 구분자는 있는데 위 패턴과 안 맞는 경우(예: "19-01-01"처럼 연도가
    # 4자리가 아닌 경우)는, 아래 2)의 "구분자 없는 숫자" 규칙으로 잘못 재해석되지
    # 않도록 여기서 바로 인식 실패로 처리합니다. 그렇지 않으면 "19-01-01"이
    # 구분자를 다 지운 뒤 6자리("190101")로 취급되어 "1919-01-01"처럼 전혀
    # 다른 날짜로 조용히 저장되는 문제가 있었습니다.
    if re.search(r"[.\-/\s]", raw):
        return raw, False

    # 2) 구분자가 없는 경우 - 순수 숫자 개수로 형식을 판단합니다.
    digits = re.sub(r"\D", "", raw)

    if len(digits) == 8:
        year, month, day = digits[:4], digits[4:6], digits[6:8]
    elif len(digits) == 6:
        # 주의: 이 프로그램은 노인복지관처럼 대상자 연령대가 높은 경우를 가정해
        #      2자리 연도를 전부 "19xx"년생으로 처리합니다.
        #      젊은 대상자가 많은 기관이라면 이 부분을 상황에 맞게 조정하세요.
        yy, month, day = digits[:2], digits[2:4], digits[4:6]
        year = "19" + yy
    else:
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
    """
    다양한 형식으로 입력된 전화번호를 "000-0000-0000" 형식으로 정규화합니다.

    지원하는 입력 예시:
        "01012345678"      (11자리, 휴대폰)      -> "010-1234-5678"
        "021234567"        (9자리, 서울 지역번호)  -> "02-123-4567"
        "0212345678"       (10자리, 서울 지역번호) -> "02-1234-5678"
        "0311234567"       (10자리, 일반 지역번호) -> "031-123-4567"

    반환값: (정규화된 문자열 또는 원본, 인식 성공 여부)
    """
    digits = re.sub(r"\D", "", raw)

    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}", True
    elif len(digits) == 10 and digits.startswith("02"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}", True
    elif len(digits) == 9 and digits.startswith("02"):
        return f"{digits[:2]}-{digits[2:5]}-{digits[5:]}", True
    elif len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}", True
    else:
        return raw.strip(), False
