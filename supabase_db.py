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
from functools import lru_cache

import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError
from supabase import create_client, Client

CLIENT_COLUMNS = [
    "id", "name", "gender", "birth_date", "address",
    "phone", "welfare_type", "note", "created_at",
    "consent_personal", "consent_sensitive", "consent_third_party", "consent_portrait",
    "consent_signed_at",
]


class DatabaseError(Exception):
    """DB 작업 중 문제가 생겼을 때, 사용자에게 보여줄 친절한 메시지를 담는 예외입니다."""
    pass


@lru_cache
def _supabase() -> Client:
    """Supabase 클라이언트를 생성해서 재사용합니다."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_SECRET_KEY"]
    except Exception as e:
        raise DatabaseError(
            "Supabase 접속 정보가 없습니다. .streamlit/secrets.toml에 "
            "SUPABASE_URL / SUPABASE_SECRET_KEY를 추가해주세요."
        ) from e
    return create_client(url, key)


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
    """모든 회원 정보를 pandas DataFrame으로 가져옵니다."""
    try:
        res = _supabase().table("clients").select("*").order("id", desc=True).execute()
    except APIError as e:
        raise DatabaseError("회원 목록을 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    return pd.DataFrame(res.data, columns=CLIENT_COLUMNS if not res.data else None)


def get_client(client_id: int) -> dict | None:
    """특정 id의 회원 정보를 한 건 가져옵니다."""
    try:
        res = _supabase().table("clients").select("*").eq("id", client_id).execute()
    except APIError as e:
        raise DatabaseError("회원 정보를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    return res.data[0] if res.data else None


def find_duplicates(name: str, birth_date: str, phone: str, exclude_id: int | None = None) -> pd.DataFrame:
    """이름+생년월일이 같거나, 전화번호가 같은 기존 회원을 찾습니다."""
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
    consent_personal, consent_sensitive, consent_third_party, consent_portrait,
):
    """새 회원을 등록합니다. consent_signed_at은 현재 시각으로 자동 기록합니다."""
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "name": name, "gender": gender, "birth_date": birth_date, "address": address,
        "phone": phone, "welfare_type": welfare_type, "note": note, "created_at": now,
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


def update_client(client_id, name, gender, birth_date, address, phone, welfare_type, note):
    """기존 회원 정보를 수정합니다 (동의 항목은 건드리지 않습니다)."""
    payload = {
        "name": name, "gender": gender, "birth_date": birth_date, "address": address,
        "phone": phone, "welfare_type": welfare_type, "note": note,
    }
    try:
        _supabase().table("clients").update(payload).eq("id", client_id).execute()
    except APIError as e:
        if "duplicate key" in str(e).lower() or getattr(e, "code", "") == "23505":
            raise DatabaseError("이미 등록된 전화번호입니다. 다른 회원과 전화번호가 중복되지 않는지 확인해주세요.") from e
        raise DatabaseError("회원 정보 수정 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e


def delete_client(client_id: int):
    """회원 정보를 삭제합니다."""
    try:
        _supabase().table("clients").delete().eq("id", client_id).execute()
    except APIError as e:
        raise DatabaseError("회원 삭제 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
