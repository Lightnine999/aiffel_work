"""SQLite 저장소. 기존 repository.py를 Store 프로토콜에 맞춰 감싼다."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from todoapp.repository import TagRepository, TodoRepository


class SqliteStore:
    """로컬 SQLite 파일 하나에 저장한다."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.todos = TodoRepository(conn)
        self.tags = TagRepository(conn)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """진짜 트랜잭션. 예외가 나면 통째로 롤백된다."""
        with self._conn:
            yield

    def close(self) -> None:
        self._conn.close()

    @property
    def connection(self) -> sqlite3.Connection:
        """테스트와 뷰 점검용. 상위 계층은 쓰지 않는다."""
        return self._conn
