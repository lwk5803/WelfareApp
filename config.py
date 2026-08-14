"""
config.py
---------
Streamlit 없이 API 키 등 시크릿(secrets)을 읽기 위한 설정 모듈입니다.
예전에는 .streamlit/secrets.toml + st.secrets를 썼는데, 프론트를 FastAPI로
완전히 옮기면서 더는 Streamlit이 설치돼 있을 필요가 없도록 이 파일로 대체합니다.

같은 값을 .env 파일(저장소 루트, git에는 안 올라감)에 넣어두면 이 모듈이 읽습니다.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def get_secret(key: str, default=None):
    """.env(또는 환경변수)에서 key 값을 읽어옵니다. 없으면 default를 돌려줍니다."""
    return os.environ.get(key, default)
