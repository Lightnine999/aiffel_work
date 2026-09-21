"""SQLite 커넥션 관리와 스키마 적용.

SQL 문장은 여기 없다. 여기는 '연결을 어떤 상태로 만들어 넘기느냐'만 책임진다.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from todoapp.config import PROJECT_ROOT

SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """커넥션 단위 설정. 트랜잭션 밖에서 실행해야 적용된다.

    - foreign_keys: SQLite 기본값이 OFF다. 꺼진 채로 두면 ON DELETE CASCADE가
      동작하지 않고 고아 행이 조용히 쌓인다.
    - recursive_triggers: 기본값이 OFF지만 명시한다. schema.sql의 트리거가
      todos를 다시 UPDATE하므로, 재귀가 켜지면 무한히 재발동한다.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA recursive_triggers = OFF")


def connect(db_path: str | Path) -> sqlite3.Connection:
    """앱이 기대하는 상태로 맞춰진 커넥션을 돌려준다.

    row_factory를 쓰는 이유: 컬럼을 이름으로 꺼내기 위함이다.
    인덱스 번호로 꺼내면 나중에 SELECT 열 순서가 바뀔 때 조용히 깨진다.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


def initialize(conn: sqlite3.Connection, schema_path: Path | None = None) -> None:
    """schema.sql을 적용한다. 전부 IF NOT EXISTS라 여러 번 불러도 안전하다."""
    path = schema_path or SCHEMA_PATH
    if not path.is_file():
        raise FileNotFoundError(f"스키마 파일을 찾을 수 없습니다: {path}")
    conn.executescript(path.read_text(encoding="utf-8"))
    # executescript는 시작 시 커밋을 하고 스크립트를 그대로 실행한다.
    # 스크립트 안의 PRAGMA가 커넥션 상태를 건드렸을 수 있으므로 다시 보장한다.
    _apply_pragmas(conn)


@contextmanager
def open_db(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """connect + initialize + 반드시 close. 짧은 작업(CLI 한 번 실행)용."""
    conn = connect(db_path)
    try:
        initialize(conn)
        yield conn
    finally:
        conn.close()
