"""SQLite 저장소. 기존 repository.py를 Store 프로토콜에 맞춰 감싼다."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator, Sequence

from todoapp.repository import TagRepository, TodoRepository


class SqliteStore:
    """로컬 SQLite 파일 하나에 저장한다."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.todos = TodoRepository(conn)
        self.tags = TagRepository(conn)

    def create_todo(
        self,
        title: str,
        *,
        notes: str | None = None,
        due_date: str | None = None,
        priority: int | str | None = None,
        tags: Sequence[str] = (),
    ) -> int:
        """할 일 insert → 태그 upsert → 연결 표 insert (3단계).

        트랜잭션을 여기서 열지 않는다. 호출부(service)가 store.transaction()으로
        감싼다 — 중첩하면 안쪽 with이 먼저 커밋해 원자성이 깨진다.
        """
        todo_id = self.todos.add(
            title, notes=notes, due_date=due_date, priority=priority
        )
        if tags:
            self.todos.replace_tags(todo_id, self._tag_ids(tags))
        return todo_id

    def set_tags(self, todo_id: int, tags: Sequence[str]) -> None:
        self.todos.replace_tags(todo_id, self._tag_ids(tags))

    def _tag_ids(self, names: Sequence[str]) -> list[int]:
        """태그 이름을 id로. 없는 이름은 그 자리에서 만든다."""
        return [self.tags.upsert(name).id for name in names]

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
