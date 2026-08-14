"""
stats.py
--------
회원 데이터를 바탕으로 통계를 계산하는 함수들을 모아둔 파일입니다.
supabase_db.py(저장), parsers.py(입력 정리)와 마찬가지로,
"통계 계산" 역할만 따로 떼어내서 이 파일에 모아뒀습니다.

main.py의 /api/stats/* 엔드포인트가 이 파일의 함수들이 돌려주는 결과(pandas Series)를
JSON으로 바꿔 돌려주면, 화면(static/js/stats.js)이 Chart.js로 그립니다.
"""

import pandas as pd
from datetime import datetime


def compute_age(birth_date_str: str) -> int | None:
    """
    생년월일 문자열("YYYY-MM-DD")로 만 나이를 계산합니다.
    형식이 이상하거나 비어있으면 계산할 수 없으므로 None을 돌려줍니다.
    """
    if not birth_date_str:
        return None
    try:
        birth = datetime.strptime(birth_date_str, "%Y-%m-%d")
    except ValueError:
        return None

    today = datetime.now()
    # 생일이 아직 안 지났으면 나이를 1살 덜 쳐주는 계산입니다.
    # (today.month, today.day) < (birth.month, birth.day) 는
    # "오늘이 생일보다 앞서 있다(아직 생일이 안 지났다)"는 뜻의 튜플 비교입니다.
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    return age


def age_group_label(age) -> str:
    """나이를 10년 단위 구간 이름으로 바꿉니다. 나이를 모르면 '미상'을 돌려줍니다."""
    # pd.isna(age): age가 None이거나 NaN(pandas가 빈 값을 표시하는 특수한 실수)인지 확인합니다.
    if age is None or pd.isna(age) or age < 0:
        return "미상"
    group = (int(age) // 10) * 10
    return f"{group}대"


def build_gender_distribution(df: pd.DataFrame) -> pd.Series:
    """성별 인원수를 계산합니다. 미입력은 '미입력'으로 표시합니다."""
    genders = df["gender"].replace("", "미입력").fillna("미입력")
    return genders.value_counts()


def build_welfare_type_distribution(df: pd.DataFrame) -> pd.Series:
    """회원 구분(일반/차상위/수급자)별 인원수를 계산합니다."""
    types = df["welfare_type"].replace("", "미입력").fillna("미입력")
    return types.value_counts()


def build_age_distribution(df: pd.DataFrame) -> pd.Series:
    """
    전체 회원의 연령대별 인원수를 계산합니다.

    주의: df["birth_date"].apply(compute_age)처럼 pandas Series에 바로 적용하면,
    None 값이 섞여있을 때 pandas가 전체를 실수(float) 타입으로 자동 변환해버려서
    나이가 30 대신 30.0으로, None이 NaN으로 바뀌는 문제가 있습니다.
    그래서 파이썬 리스트로 먼저 계산한 뒤 Series로 바꿔서, 이런 자동 변환을 피합니다.
    """
    ages = [compute_age(value) for value in df["birth_date"]]
    labels = [age_group_label(age) for age in ages]
    return pd.Series(labels).value_counts().sort_index()


def build_household_type_distribution(df: pd.DataFrame) -> pd.Series:
    """
    가구 유형별 인원수를 계산합니다. 한 회원이 여러 유형에 해당할 수 있어(예:
    "독거노인,장애인가구") 콤마로 나눠서 각각 세므로, 합계가 전체 회원 수보다
    클 수 있습니다(중복 집계 - 관리 목적상 자연스러운 일입니다).
    """
    if "household_types" not in df.columns or df.empty:
        return pd.Series(dtype=int)
    exploded = df["household_types"].fillna("").str.split(",").explode().str.strip()
    exploded = exploded[exploded != ""]
    return exploded.value_counts()


def build_disability_distribution(df: pd.DataFrame) -> pd.Series:
    """장애 유무별 인원수를 계산합니다."""
    if "has_disability" not in df.columns or df.empty:
        return pd.Series(dtype=int)
    values = df["has_disability"].replace("", "미입력").fillna("미입력")
    return values.value_counts()


def build_illness_distribution(df: pd.DataFrame) -> pd.Series:
    """질병 유무별 인원수를 계산합니다."""
    if "has_illness" not in df.columns or df.empty:
        return pd.Series(dtype=int)
    values = df["has_illness"].replace("", "미입력").fillna("미입력")
    return values.value_counts()


def build_career_distribution(df: pd.DataFrame) -> pd.Series:
    """경력(전 직업) 유무별 인원수를 계산합니다."""
    if "has_career" not in df.columns or df.empty:
        return pd.Series(dtype=int)
    values = df["has_career"].replace("", "미입력").fillna("미입력")
    return values.value_counts()


def build_join_route_distribution(df: pd.DataFrame) -> pd.Series:
    """
    가입경로별 인원수를 계산합니다. "관공서 의뢰(사유)"처럼 괄호 안에 상세 사유가
    붙어있을 수 있어서, 괄호 앞부분(기본 경로)만 잘라내서 집계합니다.
    """
    if "join_route" not in df.columns or df.empty:
        return pd.Series(dtype=int)
    base_routes = df["join_route"].fillna("").str.split("(").str[0]
    base_routes = base_routes.replace("", "미입력")
    return base_routes.value_counts()


def build_summary(df: pd.DataFrame) -> dict:
    """
    회원 목록 화면 위에 텍스트로 보여줄 간단 요약 통계를 계산합니다.

    반환값(딕셔너리)에 담기는 항목:
        total, today, this_month, male, female,
        general, near_poor, recipient
    """
    today = datetime.now().date()
    dates = pd.to_datetime(df["created_at"], errors="coerce")

    # dates.dt.date는 각 등록일시에서 "날짜"만 뽑아냅니다 (시:분:초는 버림).
    # 그 값이 오늘 날짜와 같은 행이 몇 개인지 세는 것이 "오늘 신규가입 수"입니다.
    today_count = int((dates.dt.date == today).sum())

    # 연도와 월이 모두 오늘과 같은 행의 개수 = "이번 달 신규가입 수"
    this_month_count = int(
        ((dates.dt.year == today.year) & (dates.dt.month == today.month)).sum()
    )

    gender_counts = build_gender_distribution(df)
    type_counts = build_welfare_type_distribution(df)

    return {
        "total": len(df),
        "today": today_count,
        "this_month": this_month_count,
        # .get("남", 0): 그 값이 아예 없을 수도 있으니(예: 남자 회원이 한 명도 없음),
        # 없으면 에러 대신 0을 쓰도록 기본값을 지정합니다.
        "male": int(gender_counts.get("남", 0)),
        "female": int(gender_counts.get("여", 0)),
        "general": int(type_counts.get("일반", 0)),
        "near_poor": int(type_counts.get("차상위", 0)),
        "recipient": int(type_counts.get("수급자", 0)),
    }


def build_period_breakdown(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """
    등록일시(created_at) 기준으로 지정한 기간 단위(일/월/년)별로,
    신규가입 수 + 성별 인원수 + 회원 구분별 인원수를 표(DataFrame)로 만들어 돌려줍니다.

    반환되는 표의 컬럼: 기간, 신규가입, 남, 여, 일반, 차상위, 수급자
    최근 기간이 맨 위로 오도록 정렬됩니다.
    """
    freq_map = {"일": "D", "월": "M", "년": "Y"}
    freq = freq_map[period]

    # 원본 df를 직접 건드리지 않도록 복사본에 임시 컬럼(_period)을 추가합니다.
    work_df = df.copy()
    work_df["_period"] = pd.to_datetime(work_df["created_at"], errors="coerce").dt.to_period(freq)
    work_df = work_df.dropna(subset=["_period"])

    if work_df.empty:
        return pd.DataFrame(columns=["기간", "신규가입", "남", "여", "일반", "차상위", "수급자"])

    rows = []
    # groupby("_period"): 같은 기간(예: 같은 달)에 속한 행들을 하나의 묶음(group)으로 모아줍니다.
    for period_value, group in work_df.groupby("_period"):
        gender_counts = group["gender"].replace("", "미입력").fillna("미입력").value_counts()
        type_counts = group["welfare_type"].replace("", "미입력").fillna("미입력").value_counts()

        rows.append({
            "기간": str(period_value),
            "신규가입": len(group),
            "남": int(gender_counts.get("남", 0)),
            "여": int(gender_counts.get("여", 0)),
            "일반": int(type_counts.get("일반", 0)),
            "차상위": int(type_counts.get("차상위", 0)),
            "수급자": int(type_counts.get("수급자", 0)),
        })

    result = pd.DataFrame(rows)
    return result.sort_values("기간", ascending=False).reset_index(drop=True)


def build_period_trend(df: pd.DataFrame, period: str) -> pd.Series:
    """
    등록일시(created_at) 기준으로 일/주/월/년 단위 신규 등록 추이를 계산합니다.
    period 인자: "일", "주", "월", "년" 중 하나
    """
    freq_map = {"일": "D", "주": "W", "월": "M", "년": "Y"}
    freq = freq_map[period]

    dates = pd.to_datetime(df["created_at"], errors="coerce").dropna()
    # dt.to_period(freq): 날짜를 지정한 단위(일/주/월/년)의 "구간"으로 묶어줍니다.
    grouped = dates.dt.to_period(freq).value_counts().sort_index()
    grouped.index = grouped.index.astype(str)  # 차트에 보기 좋게 문자열로 변환
    return grouped