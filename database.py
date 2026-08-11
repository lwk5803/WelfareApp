"""
database.py
-----------
회원 정보를 저장하는 SQLite 데이터베이스 관련 함수들을 모아둔 파일입니다.

관리하는 항목:
    성명, 성별, 생년월일, 주소, 전화번호, 회원 구분, 비고,
    개인정보/민감정보/제3자제공/초상권 동의 여부, 동의 확인 일시

이 파일의 모든 함수는 DB 작업 중 문제가 생기면 sqlite3의 원본 에러 대신
DatabaseError(친절한 한글 메시지)를 던집니다. app.py에서는 이 예외만 잡아서
화면에 안내 메시지를 보여주면 됩니다.

주의: get_connection() 자체가 실패하는 경우(파일 잠김, 권한 없음, 디스크 오류 등)까지
잡으려면, "연결하기"도 반드시 try 블록 '안'에 있어야 합니다. try 블록 밖에서
연결하면, 연결 실패 시 DatabaseError로 안 감싸지고 sqlite3 원본 에러가 그대로
새어나갑니다. 그래서 아래 모든 함수는 conn = None으로 미리 선언해두고,
연결부터 전부 try 블록 안에서 처리합니다.
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
    "consent_personal", "consent_sensitive", "consent_third_party", "consent_portrait",
    "consent_signed_at",
]

# 마이그레이션 대상 컬럼들: (컬럼이름, SQLite 타입) 형태로 관리합니다.
# 새 컬럼이 추가될 때마다 이 리스트에 한 줄만 추가하면 init_db()가 알아서
# "이미 있으면 건너뛰고, 없으면 추가"해줍니다.
MIGRATION_COLUMNS = [
    ("gender", "TEXT"),
    ("consent_personal", "TEXT"),
    ("consent_sensitive", "TEXT"),
    ("consent_third_party", "TEXT"),
    ("consent_portrait", "TEXT"),
    ("consent_signed_at", "TEXT"),
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
    이미 만들어져 있던 예전 버전의 DB라면, 없는 컬럼들을 자동으로 추가합니다(마이그레이션).

    반환값: 전화번호 중복 방지 인덱스가 정상적으로 만들어졌으면 True.
    연결 자체를 못 하는 등 심각한 문제가 있으면 DatabaseError를 던집니다.
    """
    conn = None
    index_created = True
    try:
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
                created_at TEXT,
                consent_personal TEXT,
                consent_sensitive TEXT,
                consent_third_party TEXT,
                consent_portrait TEXT,
                consent_signed_at TEXT
            )
            """
        )
        conn.commit()

        # ---- 마이그레이션: 예전 버전의 DB를 쓰고 계셨다면, 없는 컬럼만 골라서 추가 ----
        existing_columns = [row[1] for row in conn.execute("PRAGMA table_info(clients)").fetchall()]
        for column_name, column_type in MIGRATION_COLUMNS:
            if column_name not in existing_columns:
                conn.execute(f"ALTER TABLE clients ADD COLUMN {column_name} {column_type}")
                conn.commit()

        try:
            # 부분 유니크 인덱스: 전화번호가 빈 문자열이 아닌 경우에만 "중복 불가" 규칙을 적용합니다.
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_phone "
                "ON clients(phone) WHERE phone != ''"
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # 기존 데이터에 이미 중복된 전화번호가 있으면 인덱스를 못 만듭니다.
            # 이건 앱을 막을 정도의 심각한 문제는 아니므로, False만 돌려주고 계속 진행합니다.
            index_created = False
    except sqlite3.Error as e:
        raise DatabaseError(
            "데이터베이스 초기화 중 오류가 발생했습니다. 파일 접근 권한이나 저장 공간을 확인해주세요."
        ) from e
    finally:
        if conn is not None:
            conn.close()

    return index_created


def get_all_clients() -> pd.DataFrame:
    """모든 회원 정보를 pandas DataFrame으로 가져옵니다."""
    conn = None
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM clients ORDER BY id DESC", conn)
    except sqlite3.Error as e:
        raise DatabaseError("회원 목록을 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    finally:
        if conn is not None:
            conn.close()
    return df


def get_client(client_id: int) -> dict | None:
    """특정 id의 회원 정보를 한 건 가져옵니다."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.execute(
            f"SELECT {', '.join(CLIENT_COLUMNS)} FROM clients WHERE id = ?", (client_id,)
        )
        row = cur.fetchone()
    except sqlite3.Error as e:
        raise DatabaseError("회원 정보를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    finally:
        if conn is not None:
            conn.close()

    if row is None:
        return None
    return dict(zip(CLIENT_COLUMNS, row))


def find_duplicates(name: str, birth_date: str, phone: str, exclude_id: int | None = None) -> pd.DataFrame:
    """이름+생년월일이 같거나, 전화번호가 같은 기존 회원을 찾습니다."""
    conn = None

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
        conn = get_connection()
        df = pd.read_sql_query(query, conn, params=params)
    except sqlite3.Error as e:
        raise DatabaseError("중복 확인 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    finally:
        if conn is not None:
            conn.close()

    return df


def add_client(
    name, gender, birth_date, address, phone, welfare_type, note,
    consent_personal, consent_sensitive, consent_third_party, consent_portrait,
):
    """
    새 회원을 등록합니다.

    consent_* 매개변수는 각각 "동의함" 또는 "동의하지 않음" 문자열을 받습니다.
    등록 시각과 별개로, 동의를 확인한 시각(consent_signed_at)도 이 함수 안에서
    현재 시각으로 자동 기록합니다.
    """
    conn = None
    try:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO clients (
                name, gender, birth_date, address, phone, welfare_type, note, created_at,
                consent_personal, consent_sensitive, consent_third_party, consent_portrait,
                consent_signed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name, gender, birth_date, address, phone, welfare_type, note,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                consent_personal, consent_sensitive, consent_third_party, consent_portrait,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        raise DatabaseError("이미 등록된 전화번호입니다. 다른 회원과 전화번호가 중복되지 않는지 확인해주세요.") from e
    except sqlite3.Error as e:
        raise DatabaseError("회원 등록 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    finally:
        if conn is not None:
            conn.close()


def update_client(client_id, name, gender, birth_date, address, phone, welfare_type, note):
    """
    기존 회원 정보를 수정합니다.

    주의: 동의 항목(consent_*)은 이 함수로 수정하지 않습니다. 동의는 등록 시점의
    법적인 확인 기록이라, 일반 정보 수정 화면에서 조용히 바뀌면 안 되기 때문입니다.
    동의 내용을 다시 받아야 하는 경우는 별도의 절차로 다뤄야 합니다.
    """
    conn = None
    try:
        conn = get_connection()
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
        if conn is not None:
            conn.close()


def delete_client(client_id: int):
    """회원 정보를 삭제합니다."""
    conn = None
    try:
        conn = get_connection()
        conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError("회원 삭제 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.") from e
    finally:
        if conn is not None:
            conn.close()
