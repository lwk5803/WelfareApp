"""
database.py
-----------
대상자 정보를 저장하는 SQLite 데이터베이스 관련 함수들을 모아둔 파일입니다.

관리하는 항목 (6가지):
    성명, 생년월일, 주소, 전화번호, 대상자 계층, 비고
"""

import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "welfare.db"


def get_connection():
    """SQLite 데이터베이스 연결을 반환합니다."""
    conn = sqlite3.connect(DB_PATH)
    return conn


def init_db():
    """앱 최초 실행 시 테이블이 없으면 생성합니다."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            birth_date TEXT,
            address TEXT,
            phone TEXT,
            welfare_type TEXT,
            note TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def get_all_clients() -> pd.DataFrame:
    """모든 대상자 정보를 pandas DataFrame으로 가져옵니다."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM clients ORDER BY id DESC", conn)
    conn.close()
    return df


def get_client(client_id: int) -> dict | None:
    """특정 id의 대상자 정보를 한 건 가져옵니다."""
    conn = get_connection()
    cur = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    columns = ["id", "name", "birth_date", "address", "phone", "welfare_type", "note", "created_at"]
    return dict(zip(columns, row))


def add_client(name, birth_date, address, phone, welfare_type, note):
    """새 대상자를 등록합니다."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO clients (name, birth_date, address, phone, welfare_type, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (name, birth_date, address, phone, welfare_type, note,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def update_client(client_id, name, birth_date, address, phone, welfare_type, note):
    """기존 대상자 정보를 수정합니다."""
    conn = get_connection()
    conn.execute(
        """
        UPDATE clients
        SET name = ?, birth_date = ?, address = ?, phone = ?, welfare_type = ?, note = ?
        WHERE id = ?
        """,
        (name, birth_date, address, phone, welfare_type, note, client_id),
    )
    conn.commit()
    conn.close()


def delete_client(client_id: int):
    """대상자 정보를 삭제합니다."""
    conn = get_connection()
    conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()