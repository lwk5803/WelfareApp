"""
supabase_db.py
---------------
database.py(SQLite)와 동일한 함수 시그니처로, Supabase(Postgres)를 사용하는
버전입니다. main.py에서 `import database as db` 대신 이 파일을 쓰면
나머지 코드는 그대로 동작합니다.

Supabase 접속 정보는 .streamlit/secrets.toml의 SUPABASE_URL / SUPABASE_SECRET_KEY를
사용합니다 (service_role 키이므로 RLS를 우회하고, 이 백엔드 안에서만 써야 합니다).
"""

from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError
from supabase import create_client, Client

CLIENT_COLUMNS = [
    "id", "member_no", "name", "gender", "birth_date", "address",
    "phone", "welfare_type", "note", "created_at",
    "household_types", "has_disability", "disability_type",
    "emergency_contact_name", "emergency_contact_relation", "emergency_contact_phone",
    "join_route", "has_illness", "illness_type", "has_career", "career_type", "counselor",
    "consent_personal", "consent_sensitive", "consent_third_party", "consent_portrait",
    "consent_signed_at", "deleted_at", "photo_data",
]

# 회원 목록 화면처럼 여러 명을 한 번에 가져올 때는 사진(base64, 수십~수백KB)까지
# 매번 실어 보내면 느려지므로 뺍니다. 사진은 회원 한 명을 볼 때(get_client)만 필요합니다.
_LIST_COLUMNS = [c for c in CLIENT_COLUMNS if c != "photo_data"]


class DatabaseError(Exception):
    """DB 작업 중 문제가 생겼을 때, 사용자에게 보여줄 친절한 메시지를 담는 예외입니다."""
    pass


def _supabase() -> Client:
    """
    요청마다 새 Supabase 클라이언트를 만듭니다. 예전엔 서버 전체에서 클라이언트
    하나를 계속 재사용했는데(@lru_cache), FastAPI가 요청을 여러 스레드에서
    동시에 처리하다 보니 그 공유 클라이언트의 내부 연결 상태가 꼬여서 조회는
    빈 목록을, 등록은 알 수 없는 오류를 돌려주는 문제가 있었습니다. 매번 새로
    만들면 이 문제가 사라집니다 - 이 앱 규모(직원 몇 명)에서는 성능 손해도 미미합니다.
    """
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_SECRET_KEY"]
    except Exception as e:
        raise DatabaseError(
            "Supabase 접속 정보가 없습니다. .streamlit/secrets.toml에 "
            "SUPABASE_URL / SUPABASE_SECRET_KEY를 추가해주세요."
        ) from e
    return create_client(url, key)


def get_supabase_client() -> Client:
    """auth.py 등 다른 모듈에서도 같은 Supabase 클라이언트를 재사용할 수 있게 공개합니다."""
    return _supabase()


def init_db() -> bool:
    """
    Supabase에서는 테이블/인덱스를 SQL Editor(sql/extend_clients.sql)에서 미리
    만들어두므로, 여기서는 접속만 확인합니다.
    """
    try:
        _supabase().table("clients").select("id").limit(1).execute()
    except Exception as e:
        raise DatabaseError(
            "Supabase 연결에 실패했습니다. SUPABASE_URL/SUPABASE_SECRET_KEY와 "
            "clients 테이블이 준비되어 있는지 확인해주세요."
        ) from e
    return True


def get_all_clients() -> pd.DataFrame:
    """탈퇴(소프트 삭제) 처리되지 않은 회원 정보를 pandas DataFrame으로 가져옵니다 (사진 제외)."""
    try:
        res = (
            _supabase().table("clients").select(",".join(_LIST_COLUMNS))
            .is_("deleted_at", "null").order("id", desc=True).execute()
        )
    except APIError as e:
        raise DatabaseError("회원 목록을 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    return pd.DataFrame(res.data, columns=_LIST_COLUMNS if not res.data else None)


def get_client(client_id: int) -> dict | None:
    """특정 id의 회원 정보를 한 건 가져옵니다 (탈퇴 처리된 회원은 제외)."""
    try:
        res = _supabase().table("clients").select("*").eq("id", client_id).is_("deleted_at", "null").execute()
    except APIError as e:
        raise DatabaseError("회원 정보를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    return res.data[0] if res.data else None


def find_duplicates(name: str, birth_date: str, phone: str, exclude_id: int | None = None) -> pd.DataFrame:
    """
    이름+생년월일이 같거나, 전화번호가 같은 회원을 찾습니다. 탈퇴(소프트 삭제) 처리된
    회원도 포함해서 찾습니다 - 예전에 다녔다가 다시 등록하러 온 회원을 알아보거나,
    이미 등록된 회원을 중복 등록하지 않도록 막는 데 씁니다.
    """
    try:
        query = _supabase().table("clients").select("*")
        conditions = []
        if birth_date:
            conditions.append(f"and(name.eq.{name},birth_date.eq.{birth_date})")
        if phone:
            conditions.append(f"phone.eq.{phone}")
        if not conditions:
            return pd.DataFrame(columns=CLIENT_COLUMNS)
        query = query.or_(",".join(conditions))
        if exclude_id is not None:
            query = query.neq("id", exclude_id)
        res = query.execute()
    except APIError as e:
        raise DatabaseError("중복 확인 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    return pd.DataFrame(res.data, columns=CLIENT_COLUMNS if not res.data else None)


def add_client(
    name, gender, birth_date, address, phone, welfare_type, note,
    household_types, has_disability, disability_type,
    consent_personal, consent_sensitive, consent_third_party, consent_portrait,
    photo_data="",
    emergency_contact_name="", emergency_contact_relation="", emergency_contact_phone="",
    join_route="", has_illness="없다", illness_type="", has_career="없다", career_type="",
    counselor="",
):
    """새 회원을 등록합니다. consent_signed_at은 현재 시각으로 자동 기록합니다."""
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "name": name, "gender": gender, "birth_date": birth_date, "address": address,
        "phone": phone, "welfare_type": welfare_type, "note": note, "created_at": now,
        "household_types": household_types, "has_disability": has_disability,
        "disability_type": disability_type, "photo_data": photo_data,
        "emergency_contact_name": emergency_contact_name,
        "emergency_contact_relation": emergency_contact_relation,
        "emergency_contact_phone": emergency_contact_phone,
        "join_route": join_route, "has_illness": has_illness, "illness_type": illness_type,
        "has_career": has_career, "career_type": career_type, "counselor": counselor,
        "consent_personal": consent_personal, "consent_sensitive": consent_sensitive,
        "consent_third_party": consent_third_party, "consent_portrait": consent_portrait,
        "consent_signed_at": now,
    }
    try:
        _supabase().table("clients").insert(payload).execute()
    except APIError as e:
        if "duplicate key" in str(e).lower() or getattr(e, "code", "") == "23505":
            raise DatabaseError("이미 등록된 전화번호입니다. 다른 회원과 전화번호가 중복되지 않는지 확인해주세요.") from e
        raise DatabaseError("회원 등록 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e


def update_client(
    client_id, name, gender, birth_date, address, phone, welfare_type, note,
    household_types, has_disability, disability_type, photo_data="",
    emergency_contact_name="", emergency_contact_relation="", emergency_contact_phone="",
    join_route="", has_illness="없다", illness_type="", has_career="없다", career_type="",
    counselor="",
):
    """
    기존 회원 정보를 수정합니다 (동의 항목은 건드리지 않습니다). photo_data는 새
    사진을 촬영했을 때만 값이 오므로, 비어있으면 기존 사진을 그대로 둡니다.
    """
    payload = {
        "name": name, "gender": gender, "birth_date": birth_date, "address": address,
        "phone": phone, "welfare_type": welfare_type, "note": note,
        "household_types": household_types, "has_disability": has_disability,
        "disability_type": disability_type,
        "emergency_contact_name": emergency_contact_name,
        "emergency_contact_relation": emergency_contact_relation,
        "emergency_contact_phone": emergency_contact_phone,
        "join_route": join_route, "has_illness": has_illness, "illness_type": illness_type,
        "has_career": has_career, "career_type": career_type, "counselor": counselor,
    }
    if photo_data:
        payload["photo_data"] = photo_data
    try:
        _supabase().table("clients").update(payload).eq("id", client_id).execute()
    except APIError as e:
        if "duplicate key" in str(e).lower() or getattr(e, "code", "") == "23505":
            raise DatabaseError("이미 등록된 전화번호입니다. 다른 회원과 전화번호가 중복되지 않는지 확인해주세요.") from e
        raise DatabaseError("회원 정보 수정 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e


def delete_client(client_id: int):
    """
    회원을 실제로 지우지 않고 탈퇴 처리합니다(deleted_at 기록). 나중에 같은 사람이
    다시 등록하러 오면 find_duplicates로 이 기록을 찾아 예전 정보를 참고할 수 있습니다.
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        _supabase().table("clients").update({"deleted_at": now}).eq("id", client_id).execute()
    except APIError as e:
        raise DatabaseError("회원 삭제 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
