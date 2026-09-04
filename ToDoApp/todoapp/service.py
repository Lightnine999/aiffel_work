"""유스케이스 계층. CLI와 웹이 함께 쓴다.

여기 위쪽(cli·web)은 SQL도, sqlite3도 모른다.
트랜잭션 경계를 이 계층이 잡는 이유: '할 일 추가 + 태그 3개 연결'은
하나의 의미 단위다. 중간에 실패하면 통째로 되돌아가야 한다.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Callable, Iterable

from todoapp.models import Tag, Todo, ValidationError, parse_tag_list

# _Unset은 타입 힌트 전용으로만 가져온다. 런타임 판정은 is_set()을 쓴다.
from todoapp.repository import UNSET, _Unset, is_set
from todoapp.stores import Store

SCOPES = ("all", "active", "done", "today", "overdue", "no-due")

SCOPE_LABELS: dict[str, str] = {
    "all": "전체",
    "active": "미완료",
    "done": "완료",
    "today": "오늘까지",
    "overdue": "기한 지남",
    "no-due": "마감일 없음",
}


class TodoNotFound(LookupError):
    """그 id의 할 일이 없다."""

    def __init__(self, todo_id: int) -> None:
        super().__init__(f"{todo_id}번 할 일을 찾을 수 없습니다.")
        self.todo_id = todo_id


def _system_today() -> str:
    """오늘 날짜. DB의 date('now','localtime')와 같은 기준(로컬 시간)이다."""
    return date.today().isoformat()


class TodoService:
    def __init__(
        self,
        store: "Store | sqlite3.Connection",
        *,
        today: Callable[[], str] = _system_today,
    ) -> None:
        """저장소를 받는다. sqlite3 커넥션을 주면 SqliteStore로 감싼다.

        커넥션도 받는 이유는 하위 호환이다 — 기존 호출부와 테스트가
        TodoService(conn) 형태를 쓴다.
        """
        if isinstance(store, sqlite3.Connection):
            from todoapp.stores.sqlite_store import SqliteStore

            store = SqliteStore(store)
        self._store = store
        self._todos = store.todos
        self._tags = store.tags
        self._today = today

    # ---- 조회 ----

    def get(self, todo_id: int) -> Todo:
        todo = self._todos.get(todo_id)
        if todo is None:
            raise TodoNotFound(todo_id)
        return todo

    def list(
        self,
        scope: str = "all",
        *,
        tag: str | None = None,
        keyword: str | None = None,
    ) -> list[Todo]:
        if scope not in SCOPES:
            raise ValidationError(
                f"알 수 없는 범위입니다: {scope!r} (가능: {', '.join(SCOPES)})"
            )
        filters: dict[str, object] = {}
        if scope == "active":
            filters = {"done": False}
        elif scope == "done":
            filters = {"done": True}
        elif scope == "today":
            filters = {"done": False, "due_on_or_before": self._today(), "has_due": True}
        elif scope == "overdue":
            filters = {"done": False, "due_before": self._today(), "has_due": True}
        elif scope == "no-due":
            filters = {"done": False, "has_due": False}
        return self._todos.list(tag=tag, keyword=keyword, **filters)

    def all_tags(self) -> list[Tag]:
        return self._tags.list_all()

    def today(self) -> str:
        """오늘 날짜 문자열.

        CLI의 '오늘·내일·+7d' 해석과 웹 화면의 '기한 지남' 표시가 이걸 쓴다.
        비공개 속성 _today에 상위 계층이 손대지 않도록 공개 메서드로 노출한다.
        """
        return self._today()

    def summary(self) -> dict[str, int]:
        return {
            "total": self._todos.count_all(),
            "active": len(self.list("active")),
            "done": len(self.list("done")),
            "today": len(self.list("today")),
            "overdue": len(self.list("overdue")),
        }

    # ---- 변경 ----

    def add(
        self,
        title: str,
        *,
        notes: str | None = None,
        due: str | None = None,
        priority: int | str | None = None,
        tags: str | Iterable[str] | None = None,
    ) -> Todo:
        tag_names = parse_tag_list(tags)
        with self._store.transaction():
            todo_id = self._todos.add(title, notes=notes, due_date=due, priority=priority)
            if tag_names:
                self._todos.replace_tags(todo_id, self._resolve_tag_ids(tag_names))
        return self.get(todo_id)

    def edit(
        self,
        todo_id: int,
        *,
        title: str | _Unset = UNSET,
        notes: str | None | _Unset = UNSET,
        due: str | None | _Unset = UNSET,
        priority: int | str | _Unset = UNSET,
        tags: str | Iterable[str] | None | _Unset = UNSET,
    ) -> Todo:
        self.get(todo_id)  # 없는 id면 여기서 TodoNotFound를 던진다
        # tags를 아예 안 준 경우(UNSET)와 빈 값을 준 경우('' → 전부 제거)를 갈라야 한다
        tag_names = parse_tag_list(tags) if is_set(tags) else None
        with self._store.transaction():
            self._todos.update(
                todo_id, title=title, notes=notes, due_date=due, priority=priority
            )
            if tag_names is not None:
                self._todos.replace_tags(todo_id, self._resolve_tag_ids(tag_names))
        return self.get(todo_id)

    def complete(self, todo_id: int) -> Todo:
        return self._set_done(todo_id, True)

    def reopen(self, todo_id: int) -> Todo:
        return self._set_done(todo_id, False)

    def toggle(self, todo_id: int) -> Todo:
        return self._set_done(todo_id, not self.get(todo_id).is_done)

    def delete(self, todo_id: int) -> None:
        with self._store.transaction():
            if not self._todos.delete(todo_id):
                raise TodoNotFound(todo_id)

    # ---- 내부 ----

    def _set_done(self, todo_id: int, done: bool) -> Todo:
        with self._store.transaction():
            if not self._todos.set_done(todo_id, done):
                raise TodoNotFound(todo_id)
        return self.get(todo_id)

    def _resolve_tag_ids(self, names: tuple[str, ...]) -> list[int]:
        """태그 이름을 id로. 없는 이름은 그 자리에서 만든다."""
        return [self._tags.upsert(name).id for name in names]
