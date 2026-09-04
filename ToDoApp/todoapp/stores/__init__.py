"""저장소 이음새(seam).

`TodoService`는 SQLite도 Supabase도 모른다. 이 프로토콜만 안다.
저장소를 갈아끼울 때 손대는 곳은 이 패키지 안쪽뿐이다.
"""

from __future__ import annotations

from typing import ContextManager, Protocol, runtime_checkable


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

    def add(self, title: str, **kwargs) -> int: ...
    def get(self, todo_id: int): ...
    def list(self, **filters) -> list: ...
    def update(self, todo_id: int, **fields) -> bool: ...
    def set_done(self, todo_id: int, done: bool) -> bool: ...
    def delete(self, todo_id: int) -> bool: ...
    def replace_tags(self, todo_id: int, tag_ids) -> None: ...
    def load_tags(self, todo_ids) -> dict: ...
    def count_all(self) -> int: ...


@runtime_checkable
class Store(Protocol):
    """저장소 한 벌. `.todos`·`.tags`와 트랜잭션 경계를 제공한다."""

    todos: TodoStore
    tags: TagStore

    def transaction(self) -> ContextManager[None]:
        """여러 문장을 한 덩어리로 묶는다.

        SQLite는 실제 트랜잭션이다. Supabase(PostgREST)는 클라이언트
        트랜잭션이 없어서 no-op이고, 원자성이 필요한 작업은 서버 함수(RPC)로
        처리한다. 이 차이는 각 구현의 주석에 적어둔다.
        """
        ...


__all__ = ["Store", "TodoStore", "TagStore", "build_store"]


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
