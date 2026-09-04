"""저장소 이음새(seam).

`TodoService`는 SQLite도 Supabase도 모른다. 이 프로토콜만 안다.
저장소를 갈아끼울 때 손대는 곳은 이 패키지 안쪽뿐이다.
"""

from __future__ import annotations

from typing import ContextManager, Protocol, Sequence, runtime_checkable


@runtime_checkable
class TagStore(Protocol):
    """태그 사전 접근."""

    def upsert(self, name: str, color: str | None = None): ...
    def get(self, tag_id: int): ...
    def get_by_name(self, name: str): ...
    def list_all(self) -> list: ...


@runtime_checkable
class TodoStore(Protocol):
    """할 일 접근."""

    def get(self, todo_id: int): ...
    def list(self, **filters) -> list: ...
    def update(self, todo_id: int, **fields) -> bool: ...
    def set_done(self, todo_id: int, done: bool) -> bool: ...
    def delete(self, todo_id: int) -> bool: ...
    def count_all(self) -> int: ...


@runtime_checkable
class Store(Protocol):
    """저장소 한 벌. `.todos`·`.tags`와 트랜잭션 경계를 제공한다."""

    todos: TodoStore
    tags: TagStore

    def create_todo(
        self,
        title: str,
        *,
        notes: str | None = ...,
        due_date: str | None = ...,
        priority: int | str | None = ...,
        tags: "Sequence[str]" = ...,
    ) -> int:
        """할 일을 만들고 태그를 붙인다. 태그는 **이름**으로 받는다.

        이름 → id 해석을 저장소 안에 두는 이유: SQLite는 upsert 후 연결 표에
        insert하는 2단계이고, Supabase는 서버 함수 한 번이다. 단계 수는
        저장 방식의 문제이므로 서비스가 알 필요가 없다.
        """
        ...

    def set_tags(self, todo_id: int, tags: "Sequence[str]") -> None:
        """이 할 일의 태그를 주어진 이름 목록으로 통째로 교체한다."""
        ...

    def transaction(self) -> ContextManager[None]:
        """여러 문장을 한 덩어리로 묶는다.

        SQLite는 실제 트랜잭션이다. Supabase(PostgREST)는 클라이언트
        트랜잭션이 없어서 no-op이고, 원자성이 필요한 작업은 서버 함수(RPC)로
        처리한다. 이 차이는 각 구현의 주석에 적어둔다.
        """
        ...


__all__ = ["Store", "TodoStore", "TagStore", "build_store", "coerce_store"]


def build_store(backend: str | None = None) -> Store:
    """설정에 맞는 저장소를 만든다. 여기가 유일한 분기점이다."""
    from todoapp.config import get_storage_backend

    name = (backend or get_storage_backend()).strip().lower()
    if name == "sqlite":
        from todoapp.config import get_db_path
        from todoapp.database import connect, initialize
        from todoapp.stores.sqlite_store import SqliteStore

        conn = connect(get_db_path())
        initialize(conn)
        return SqliteStore(conn)
    if name == "supabase":
        raise NotImplementedError(
            "Supabase 저장소는 아직 구현되지 않았습니다. .env의 STORAGE=sqlite 로 두세요."
        )
    raise ValueError(f"알 수 없는 STORAGE 값입니다: {name!r} (가능: sqlite, supabase)")


def coerce_store(obj: object) -> Store:
    """Store가 아니면 감싼다. sqlite3 커넥션을 주면 SqliteStore로 만든다.

    하위 호환용이다 — 기존 호출부와 테스트가 TodoService(conn) 형태를 쓴다.
    이 변환을 service가 아니라 여기에 두는 이유: 저장소 종류를 아는 곳이
    한 군데여야 한다. service가 SqliteStore를 알면 이음새가 새는 것이다.
    """
    import sqlite3

    if isinstance(obj, sqlite3.Connection):
        from todoapp.stores.sqlite_store import SqliteStore

        return SqliteStore(obj)
    return obj  # type: ignore[return-value]
