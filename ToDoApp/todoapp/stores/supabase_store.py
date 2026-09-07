"""Supabase(Postgres) 저장소.

SQLite 구현과 다른 점 세 가지, 그리고 그 이유:

1. **트랜잭션이 없다.** PostgREST는 요청 하나가 문장 하나다. 여러 문장을
   한 덩어리로 묶어야 하는 작업(할 일 추가 + 태그 연결)은 Postgres 함수(RPC)로
   서버에서 처리한다. `transaction()`은 no-op이다.
2. **user_id를 앱이 넣지 않는다.** DB의 `default auth.uid()`가 채운다.
   앱이 넣으면 '누구인지'의 출처가 두 곳으로 갈라진다.
3. **와일드카드가 `*`다.** SQLite의 `%`가 아니다. 이스케이프 대상이 다르다.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, Sequence

from todoapp.models import (
    UNSET,
    Tag,
    Todo,
    normalize_color,
    normalize_due_date,
    normalize_priority,
    normalize_tag_name,
    normalize_title,
    _Unset,
    is_set,
)

if TYPE_CHECKING:
    from supabase import Client

# 임베드 조회로 태그를 함께 가져온다. 할 일마다 따로 부르면 N+1이 된다.
_TODO_SELECT = (
    "id, title, notes, is_done, due_date, priority,"
    " created_at, updated_at, completed_at,"
    " todo_tags(tags(id, name, color))"
)

# PostgREST 필터 문법에서 특별한 뜻을 갖는 글자.
# %는 여기서 특별하지 않다 (SQLite와 다른 점).
_SPECIAL = ("\\", "*", ",", "(", ")", ".", ":")


def escape_postgrest_pattern(value: str) -> str:
    r"""ilike 패턴·or_ 필터에서 특별한 글자를 무력화한다.

    `*`를 그대로 두면 사용자가 '*'를 검색할 때 전부 일치해 버린다.
    `,`를 그대로 두면 or_() 필터가 그 자리에서 쪼개져 엉뚱한 조건이 된다.
    역슬래시를 가장 먼저 바꿔야 방금 붙인 이스케이프 문자가 이중으로 바뀌지 않는다.
    """
    for char in _SPECIAL:
        value = value.replace(char, "\\" + char)
    return value


def _row_to_tag(row: dict[str, Any]) -> Tag:
    return Tag(id=row["id"], name=row["name"], color=row["color"])


def _row_to_todo(row: dict[str, Any]) -> Todo:
    """행을 도메인 객체로. Postgres는 boolean·date가 진짜 타입이라 변환이 없다."""
    embedded = row.get("todo_tags") or []
    tags = [_row_to_tag(item["tags"]) for item in embedded if item.get("tags")]
    tags.sort(key=lambda t: t.name.casefold())
    return Todo(
        id=row["id"],
        title=row["title"],
        notes=row.get("notes"),
        is_done=bool(row.get("is_done")),
        due_date=row.get("due_date"),
        priority=row.get("priority", 2),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        completed_at=row.get("completed_at"),
        tags=tuple(tags),
    )


class SupabaseTagStore:
    """태그 사전. 유일성 범위가 (user_id, name)이라 남의 태그와 충돌하지 않는다."""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def upsert(self, name: str, color: str | None = None) -> Tag:
        clean = normalize_tag_name(name)
        if color is not None:
            normalize_color(color)  # 형식 검증만 (RPC는 색상을 바꾸지 않는다)
        ids = self._client.rpc("upsert_tags", {"p_names": [clean]}).execute().data
        tag_id = ids[0] if ids else None
        found = self.get(tag_id) if tag_id else None
        return found or Tag(id=tag_id, name=clean)

    def get(self, tag_id: int) -> Tag | None:
        rows = (
            self._client.table("tags")
            .select("id, name, color")
            .eq("id", tag_id)
            .limit(1)
            .execute()
            .data
        )
        return _row_to_tag(rows[0]) if rows else None

    def get_by_name(self, name: str) -> Tag | None:
        rows = (
            self._client.table("tags")
            .select("id, name, color")
            .eq("name", normalize_tag_name(name))
            .limit(1)
            .execute()
            .data
        )
        return _row_to_tag(rows[0]) if rows else None

    def list_all(self) -> list[Tag]:
        rows = (
            self._client.table("tags")
            .select("id, name, color")
            .order("name")
            .execute()
            .data
        )
        return [_row_to_tag(r) for r in rows or []]


class SupabaseTodoStore:
    """할 일. 원자성이 필요한 작업은 RPC로 서버에 넘긴다."""

    def __init__(self, client: "Client") -> None:
        self._client = client

    # ---- 쓰기 ----

    def add(
        self,
        title: str,
        *,
        notes: str | None = None,
        due_date: str | None = None,
        priority: int | str | None = None,
        tags: Sequence[str] = (),
    ) -> int:
        """할 일과 태그를 서버에서 한 덩어리로 만든다.

        insert와 태그 연결을 따로 보내면 중간에 실패했을 때 태그 없는 할 일이
        남는다. RPC 함수 하나가 트랜잭션 안에서 처리한다.
        """
        clean_notes = notes.strip() if isinstance(notes, str) and notes.strip() else None
        params = {
            "p_title": normalize_title(title),
            "p_notes": clean_notes,
            "p_due_date": normalize_due_date(due_date),
            "p_priority": normalize_priority(priority),
            "p_tags": [normalize_tag_name(t) for t in tags],
        }
        return int(self._client.rpc("create_todo_with_tags", params).execute().data)

    def update(
        self,
        todo_id: int,
        *,
        title: str | _Unset = UNSET,
        notes: str | None | _Unset = UNSET,
        due_date: str | None | _Unset = UNSET,
        priority: int | str | _Unset = UNSET,
    ) -> bool:
        patch: dict[str, Any] = {}
        if is_set(title):
            patch["title"] = normalize_title(title)
        if is_set(notes):
            patch["notes"] = (
                notes.strip() if isinstance(notes, str) and notes.strip() else None
            )
        if is_set(due_date):
            patch["due_date"] = normalize_due_date(due_date)
        if is_set(priority):
            patch["priority"] = normalize_priority(priority)
        if not patch:
            return False
        rows = (
            self._client.table("todos")
            .update(patch)
            .eq("id", todo_id)
            .execute()
            .data
        )
        return bool(rows)

    def set_done(self, todo_id: int, done: bool) -> bool:
        """completed_at·updated_at은 Postgres 트리거가 채운다."""
        rows = (
            self._client.table("todos")
            .update({"is_done": bool(done)})
            .eq("id", todo_id)
            .execute()
            .data
        )
        return bool(rows)

    def delete(self, todo_id: int) -> bool:
        """todo_tags 연결은 on delete cascade가 정리한다."""
        rows = self._client.table("todos").delete().eq("id", todo_id).execute().data
        return bool(rows)

    def set_tags(self, todo_id: int, tags: Sequence[str]) -> None:
        """태그를 이름으로 통째로 교체한다. 삭제와 삽입이 서버에서 한 덩어리다."""
        self._client.rpc(
            "set_todo_tags",
            {
                "p_todo_id": todo_id,
                "p_tags": [normalize_tag_name(t) for t in tags],
            },
        ).execute()

    # ---- 조회 ----

    def get(self, todo_id: int) -> Todo | None:
        rows = (
            self._client.table("todos")
            .select(_TODO_SELECT)
            .eq("id", todo_id)
            .limit(1)
            .execute()
            .data
        )
        return _row_to_todo(rows[0]) if rows else None

    def list(
        self,
        *,
        done: bool | None = None,
        tag: str | None = None,
        keyword: str | None = None,
        due_on_or_before: str | None = None,
        due_before: str | None = None,
        has_due: bool | None = None,
    ) -> list[Todo]:
        select = _TODO_SELECT
        if tag is not None:
            # !inner 로 태그가 붙은 행만 남긴다. 임베드라 행이 중복되지 않는다.
            select = select.replace(
                "todo_tags(tags(id, name, color))",
                "todo_tags!inner(tags!inner(id, name, color))",
            )
        query = self._client.table("todos").select(select)

        if tag is not None:
            query = query.eq("todo_tags.tags.name", normalize_tag_name(tag))
        if done is not None:
            query = query.eq("is_done", bool(done))
        if due_on_or_before is not None:
            query = query.lte("due_date", normalize_due_date(due_on_or_before))
        if due_before is not None:
            query = query.lt("due_date", normalize_due_date(due_before))
        if has_due is not None:
            # PostgREST에서 'is not null'은 not_.is_(col, "null") 이다.
            # is_(col, "not.null")로 쓰면 is.not.null 이 되어 파싱 오류가 난다
            # (PGRST100). 가짜 클라이언트 테스트로는 못 잡는 종류의 버그다 —
            # 통합 테스트가 잡았다.
            query = (
                query.not_.is_("due_date", "null")
                if has_due
                else query.is_("due_date", "null")
            )
        if keyword is not None and str(keyword).strip():
            pattern = f"*{escape_postgrest_pattern(str(keyword).strip())}*"
            query = query.or_(f"title.ilike.{pattern},notes.ilike.{pattern}")

        # SQLite 구현과 같은 정렬: 미완료 → 마감 임박 → 우선순위 → 등록순
        query = (
            query.order("is_done")
            .order("due_date", nullsfirst=False)
            .order("priority")
            .order("id")
        )
        rows = query.execute().data or []
        return [_row_to_todo(r) for r in rows]

    def count_all(self) -> int:
        return len(self._client.table("todos").select("id").execute().data or [])


class SupabaseStore:
    """클라우드 Postgres 저장소. RLS가 '내 행만' 보이게 강제한다."""

    def __init__(self, client: "Client", user_id: str | None = None) -> None:
        self._client = client
        self.user_id = user_id
        # build_store가 갱신된 토큰을 여기 담는다. 호출부가 저장 여부를 판단한다.
        self.tokens = None
        self.todos = SupabaseTodoStore(client)
        self.tags = SupabaseTagStore(client)

    def create_todo(
        self,
        title: str,
        *,
        notes: str | None = None,
        due_date: str | None = None,
        priority: int | str | None = None,
        tags: Sequence[str] = (),
    ) -> int:
        """서버 함수 한 번. 할 일 insert와 태그 연결이 한 트랜잭션 안이다."""
        return self.todos.add(
            title, notes=notes, due_date=due_date, priority=priority, tags=tags
        )

    def set_tags(self, todo_id: int, tags: Sequence[str]) -> None:
        self.todos.set_tags(todo_id, tags)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """no-op이다. PostgREST에는 클라이언트 트랜잭션이 없다.

        원자성이 필요한 작업은 이미 RPC 함수로 서버에서 처리하므로 여기서
        할 일이 없다. 예외를 삼키지 않고 그대로 올려보낸다 — 삼키면 호출부가
        실패를 성공으로 오해한다.
        """
        yield

    def close(self) -> None:
        """대응하는 자원이 없다 (HTTP 클라이언트는 스스로 관리된다)."""
