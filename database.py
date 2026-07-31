"""
database.py
-----------
<<<<<<< HEAD
회원 정보를 저장하는 SQLite 데이터베이스 관련 함수들을 모아둔 파일입니다.

관리하는 항목 (7가지):
    성명, 성별, 생년월일, 주소, 전화번호, 회원 구분, 비고

이 파일의 모든 함수는 DB 작업 중 문제가 생기면 sqlite3의 원본 에러 대신
DatabaseError(친절한 한글 메시지)를 던집니다. app.py에서는 이 예외만 잡아서
화면에 안내 메시지를 보여주면 됩니다.
=======
대상자 정보를 저장하는 SQLite 데이터베이스 관련 함수들을 모아둔 파일입니다.

관리하는 항목 (6가지):
    성명, 생년월일, 주소, 전화번호, 대상자 계층, 비고
>>>>>>> cf95d36846065d68c68ec7c89aec76a193b6c4e3
"""

import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "welfare.db"

# get_client()에서 SELECT할 컬럼 순서를 명시적으로 정해둡니다.
# "SELECT *"로 가져오면 실제 테이블에 저장된 물리적 순서를 따르는데,
# 나중에 ALTER TABLE로 컬럼을 추가하면 그 컬럼이 항상 맨 뒤에 붙어서
# 우리가 원하는 순서와 어긋날 수 있습니다. 그래서 컬럼명을 직접 나열해서
# "이 순서로 값을 달라"고 명확하게 요청합니다.
CLIENT_COLUMNS = [
    "id", "name", "gender", "birth_date", "address",
    "phone", "welfare_type", "note", "created_at",
]


class DatabaseError(Exception):
    """DB 작업 중 문제가 생겼을 때, 사용자에게 보여줄 친절한 메시지를 담는 예외입니다."""
    pass


def get_connection():
    """SQLite 데이터베이스 연결을 반환합니다."""
    conn = sqlite3.connect(DB_PATH)
    return conn


def init_db() -> bool:
    """
    앱 최초 실행 시 테이블이 없으면 생성하고, 전화번호 중복 방지용 인덱스를 만듭니다.
    이미 만들어져 있던 예전 버전의 DB라면, gender 컬럼이 없을 경우 추가합니다(마이그레이션).

    반환값: 전화번호 중복 방지 인덱스가 정상적으로 만들어졌으면 True.
    """
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT,
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

    # ---- 마이그레이션: 예전 버전(gender 컬럼이 없던 시절)의 DB를 쓰고 계셨다면 ----
    # PRAGMA table_info로 지금 테이블에 실제로 어떤 컬럼이 있는지 확인하고,
    # gender가 없으면 추가합니다. SQLite는 "컬럼이 없을 때만 추가"하는 문법이
    # 따로 없어서, 이렇게 먼저 확인 후 필요할 때만 ALTER TABLE을 실행합니다.
    existing_columns = [row[1] for row in conn.execute("PRAGMA table_info(clients)").fetchall()]
    if "gender" not in existing_columns:
        conn.execute("ALTER TABLE clients ADD COLUMN gender TEXT")
        conn.commit()

    index_created = True
    try:
        # 부분 유니크 인덱스: 전화번호가 빈 문자열이 아닌 경우에만 "중복 불가" 규칙을 적용합니다.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_phone "
            "ON clients(phone) WHERE phone != ''"
        )
        conn.commit()
    except sqlite3.IntegrityError:
        index_created = False
    finally:
        conn.close()

    return index_created


def get_all_clients() -> pd.DataFrame:
    """모든 회원 정보를 pandas DataFrame으로 가져옵니다."""
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM clients ORDER BY id DESC", conn)
    except sqlite3.Error as e:
        raise DatabaseError("회원 목록을 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    finally:
        conn.close()
    return df


def get_client(client_id: int) -> dict | None:
    """특정 id의 회원 정보를 한 건 가져옵니다."""
    conn = get_connection()
    try:
        cur = conn.execute(
            f"SELECT {', '.join(CLIENT_COLUMNS)} FROM clients WHERE id = ?", (client_id,)
        )
        row = cur.fetchone()
    except sqlite3.Error as e:
        raise DatabaseError("회원 정보를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    finally:
        conn.close()

    if row is None:
        return None
    return dict(zip(CLIENT_COLUMNS, row))


def find_duplicates(name: str, birth_date: str, phone: str, exclude_id: int | None = None) -> pd.DataFrame:
    """이름+생년월일이 같거나, 전화번호가 같은 기존 회원을 찾습니다."""
    conn = get_connection()

    query = """
        SELECT * FROM clients
        WHERE (name = ? AND birth_date = ? AND birth_date != '')
           OR (phone = ? AND phone != '')
    """
    params = [name, birth_date, phone]

    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)

    try:
        df = pd.read_sql_query(query, conn, params=params)
    except sqlite3.Error as e:
        raise DatabaseError("중복 확인 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    finally:
        conn.close()

    return df


def add_client(name, gender, birth_date, address, phone, welfare_type, note):
    """새 회원을 등록합니다."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO clients (name, gender, birth_date, address, phone, welfare_type, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, gender, birth_date, address, phone, welfare_type, note,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        raise DatabaseError("이미 등록된 전화번호입니다. 다른 회원과 전화번호가 중복되지 않는지 확인해주세요.") from e
    except sqlite3.Error as e:
        raise DatabaseError("회원 등록 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    finally:
        conn.close()


def update_client(client_id, name, gender, birth_date, address, phone, welfare_type, note):
    """기존 회원 정보를 수정합니다."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE clients
            SET name = ?, gender = ?, birth_date = ?, address = ?, phone = ?, welfare_type = ?, note = ?
            WHERE id = ?
            """,
            (name, gender, birth_date, address, phone, welfare_type, note, client_id),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        raise DatabaseError("이미 등록된 전화번호입니다. 다른 회원과 전화번호가 중복되지 않는지 확인해주세요.") from e
    except sqlite3.Error as e:
        raise DatabaseError("회원 정보 수정 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    finally:
        conn.close()


def delete_client(client_id: int):
    """회원 정보를 삭제합니다."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError("회원 삭제 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    finally:
        conn.close()
