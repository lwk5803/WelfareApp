"""
auth.py
-------
로그인 및 권한 검사를 담당합니다. 비밀번호 저장/검증 자체는 Supabase Auth가
대신 처리하고(우리는 비밀번호를 직접 다루지 않습니다), 우리는 로그인 시
발급되는 JWT(access_token)가 진짜 Supabase가 발급한 것인지만 검증합니다.

역할(role)은 두 단계입니다:
    - staff: 회원 등록/수정 가능, 삭제 불가 (기본값)
    - admin: 등록/수정/삭제 모두 가능

새 직원 계정은 Supabase 대시보드 > Authentication > Users에서 만들면 됩니다.
관리자로 지정하려면 SQL Editor에서:
    update profiles set role = 'admin' where email = '담당자 이메일';
"""
from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException, Request
from jwt import PyJWKClient

import config
import supabase_db as db


class AuthError(Exception):
    """로그인/인증 중 문제가 생겼을 때, 사용자에게 보여줄 친절한 메시지를 담는 예외입니다."""
    pass


def _get_role(user_id: str) -> str:
    client = db.get_supabase_client()
    res = client.table("profiles").select("role").eq("id", user_id).execute()
    return res.data[0]["role"] if res.data else "staff"


def login(email: str, password: str) -> dict:
    """이메일/비밀번호로 로그인하고, access_token/refresh_token과 역할(role)을 돌려줍니다."""
    client = db.get_supabase_client()
    try:
        res = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as e:
        raise AuthError("이메일 또는 비밀번호가 올바르지 않습니다.") from e

    return {
        "access_token": res.session.access_token,
        "refresh_token": res.session.refresh_token,
        "email": res.user.email,
        "role": _get_role(res.user.id),
    }


def refresh(refresh_token: str) -> dict:
    """
    refresh_token으로 로그인을 갱신합니다. access_token은 발급 후 1시간 정도만 유효하지만,
    브라우저에 저장해둔 refresh_token으로 새로고침할 때마다 다시 로그인하지 않고 조용히
    갱신할 수 있습니다. Supabase는 갱신할 때마다 refresh_token 자체도 새로 발급합니다
    (예전 refresh_token은 이후 못 씀) - 그래서 응답에 새 refresh_token도 같이 돌려줍니다.
    """
    client = db.get_supabase_client()
    try:
        res = client.auth.refresh_session(refresh_token)
    except Exception as e:
        raise AuthError("로그인이 만료되었습니다. 다시 로그인해주세요.") from e

    return {
        "access_token": res.session.access_token,
        "refresh_token": res.session.refresh_token,
        "email": res.user.email,
        "role": _get_role(res.user.id),
    }


@lru_cache
def _jwks_client() -> PyJWKClient:
    jwks_url = config.get_secret("SUPABASE_JWKS_URL")
    if not jwks_url:
        raise AuthError("SUPABASE_JWKS_URL이 설정되지 않았습니다. .env 파일을 확인해주세요.")
    return PyJWKClient(jwks_url)


def _decode_token(token: str) -> dict:
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        # leeway: 이 서버와 Supabase 서버의 시계가 몇 초 어긋나 있어도(흔한 일입니다)
        # "발급 시각이 아직 안 됐다"고 잘못 거부하지 않도록 약간의 오차를 허용합니다.
        payload = jwt.decode(
            token, signing_key.key, algorithms=["ES256", "RS256"], audience="authenticated",
            leeway=30,
        )
    except Exception as e:
        raise AuthError("로그인이 만료되었거나 유효하지 않습니다. 다시 로그인해주세요.") from e
    return payload


def get_user_from_token(token: str) -> dict:
    """access_token(JWT) 문자열을 검증하고, 사용자 정보를 돌려줍니다. 실패하면 AuthError를 던집니다."""
    payload = _decode_token(token)
    user_id = payload["sub"]
    return {"user_id": user_id, "email": payload.get("email", ""), "role": _get_role(user_id)}


def require_user(request: Request, authorization: str = Header(default="")) -> dict:
    """
    FastAPI 엔드포인트에서 Depends(require_user)로 쓰면, 로그인된 사용자만 통과시킵니다.

    토큰은 두 곳에서 찾습니다: 기존처럼 Authorization: Bearer 헤더(외부/스크립트 호출용),
    또는 access_token 쿠키(브라우저 화면의 JS fetch 호출용 - 같은 출처라 쿠키가 자동으로
    실려오므로 프론트에서 토큰을 따로 다루지 않아도 됩니다).
    """
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    if not token:
        token = request.cookies.get("access_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    try:
        return get_user_from_token(token)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


def require_admin(user: dict = Depends(require_user)) -> dict:
    """FastAPI 엔드포인트에서 Depends(require_admin)으로 쓰면, 관리자만 통과시킵니다."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="관리자만 할 수 있는 작업입니다.")
    return user
