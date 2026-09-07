"""SQL 전담 계층.

앱 안에서 SQL 문자열이 존재하는 곳은 이 파일과 db/schema.sql 뿐이다.
상위 계층(service·cli·web)은 SQL을 모른다.
"""

from __future__ import annotations

import sqlite3
from typing import Sequence

from todoapp.models import (
    DEFAULT_TAG_COLOR,
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


def row_to_tag(row: sqlite3.Row) -> Tag:
    return Tag(id=row["id"], name=row["name"], color=row["color"])


class TagRepository:
    """태그 사전. 이름은 대소문자를 무시하고 유일하다."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, name: str, color: str | None = None) -> Tag:
        """있으면 가져오고 없으면 만든다.

        color를 주면 갱신하고, 생략하면(None) 기존 색상을 지킨다.
        이름 표기는 먼저 저장된 쪽을 유지한다 — 'Study'가 있으면 'study'로
        넣어도 'Study'가 남는다. tags.name이 COLLATE NOCASE이기 때문이다.
        """
        clean_name = normalize_tag_name(name)
        clean_color = normalize_color(color) if color is not None else None
        # DO UPDATE에서 excluded.color를 쓰면 안 된다. VALUES의 COALESCE가
        # 이미 기본색을 채워 넣어서 excluded.color가 절대 NULL이 되지 않고,
        # 색상을 생략했을 때도 기존 색상을 기본색으로 덮어쓴다.
        # 이름 있는 파라미터를 직접 참조해 '생략'과 '기본색 지정'을 구분한다.
        row = self._conn.execute(
            """
            INSERT INTO tags (name, color)
            VALUES (:name, COALESCE(:color, :default_color))
            ON CONFLICT(name) DO UPDATE
                SET color = COALESCE(:color, tags.color)
            RETURNING id, name, color
            """,
            {"name": clean_name, "color": clean_color, "default_color": DEFAULT_TAG_COLOR},
        ).fetchone()
        return row_to_tag(row)

    def get(self, tag_id: int) -> Tag | None:
        row = self._conn.execute(
            "SELECT id, name, color FROM tags WHERE id = ?", (tag_id,)
        ).fetchone()
        return row_to_tag(row) if row else None

    def get_by_name(self, name: str) -> Tag | None:
        """이름으로 찾는다. 열 콜레이션이 NOCASE라 대소문자를 무시한다."""
        row = self._conn.execute(
            "SELECT id, name, color FROM tags WHERE name = ?",
            (normalize_tag_name(name),),
        ).fetchone()
        return row_to_tag(row) if row else None

    def list_all(self) -> list[Tag]:
        rows = self._conn.execute(
            "SELECT id, name, color FROM tags ORDER BY name COLLATE NOCASE ASC"
        ).fetchall()
        return [row_to_tag(r) for r in rows]

    def delete_unused(self) -> int:
        """어떤 할 일에도 붙지 않은 태그를 지운다. 지운 개수를 돌려준다."""
        cursor = self._conn.execute(
            "DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM todo_tags)"
        )
        return cursor.rowcount


def row_to_todo(row: sqlite3.Row, tags: tuple[Tag, ...] = ()) -> Todo:
    """DB 행을 도메인 객체로. is_done 0/1 → bool 변환은 여기서만 한다."""
    return Todo(
        id=row["id"],
        title=row["title"],
        notes=row["notes"],
        is_done=bool(row["is_done"]),
        due_date=row["due_date"],
        priority=row["priority"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
        tags=tags,
    )


def _clean_notes(notes: str | None) -> str | None:
    """공백만 있는 메모는 없는 것으로 본다."""
    return notes.strip() if isinstance(notes, str) and notes.strip() else None


def _escape_like(value: str) -> str:
    r"""LIKE 패턴에서 특별한 뜻을 가진 글자를 무력화한다.

    escape하지 않으면 사용자가 '%'를 검색할 때 전체가 일치해 버린다.
    역슬래시를 먼저 바꿔야 한다 — 나중에 하면 방금 붙인 escape 문자까지
    이중으로 바뀐다.
    """
    return value.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")


_TAG_EXISTS_SQL = """EXISTS (
                       SELECT 1 FROM todo_tags tt
                         JOIN tags g ON g.id = tt.tag_id
                        WHERE tt.todo_id = todos.id AND g.name = ?
                   )"""

# LIKE 검색은 제목과 메모 두 열을 본다. ESCAPE로 사용자가 넣은 %·_를 무력화한다.
_KEYWORD_SQL = r"(title LIKE ? ESCAPE '\' OR COALESCE(notes, '') LIKE ? ESCAPE '\')"


def _build_list_where(
    *,
    done: bool | None,
    tag: str | None,
    keyword: str | None,
    due_on_or_before: str | None,
    due_before: str | None,
    has_due: bool | None,
    priority: int | str | None = None,
) -> tuple[str, list[object]]:
    """필터를 WHERE 절과 바인딩 값으로 조립한다. None은 '거르지 않음'."""
    clauses: list[str] = []
    params: list[object] = []

    if done is not None:
        clauses.append("is_done = ?")
        params.append(1 if done else 0)

    if tag is not None:
        # JOIN이 아니라 EXISTS를 쓴다. JOIN으로 걸면 태그가 여러 개 붙은
        # 할 일이 여러 행으로 튀어나온다.
        clauses.append(_TAG_EXISTS_SQL)
        params.append(normalize_tag_name(tag))

    if keyword is not None and str(keyword).strip():
        pattern = f"%{_escape_like(str(keyword).strip())}%"
        clauses.append(_KEYWORD_SQL)
        params.extend([pattern, pattern])

    if due_on_or_before is not None:
        clauses.append("due_date IS NOT NULL AND due_date <= ?")
        params.append(normalize_due_date(due_on_or_before))

    if due_before is not None:
        clauses.append("due_date IS NOT NULL AND due_date < ?")
        params.append(normalize_due_date(due_before))

    if has_due is not None:
        clauses.append("due_date IS NOT NULL" if has_due else "due_date IS NULL")

    if priority is not None:
        # 이름(high)도 숫자(1)도 받는다. 잘못된 값은 여기서 ValidationError.
        clauses.append("priority = ?")
        params.append(normalize_priority(priority))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


_TODO_COLUMNS = """
    id, title, notes, is_done, due_date, priority,
    created_at, updated_at, completed_at
"""


class TodoRepository:
    """할 일 CRUD와 태그 연결. 트랜잭션 경계는 상위(service)가 잡는다."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(
        self,
        title: str,
        *,
        notes: str | None = None,
        due_date: str | None = None,
        priority: int | str | None = None,
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO todos (title, notes, due_date, priority) VALUES (?, ?, ?, ?)",
            (
                normalize_title(title),
                _clean_notes(notes),
                normalize_due_date(due_date),
                normalize_priority(priority),
            ),
        )
        return int(cursor.lastrowid)

    def get(self, todo_id: int) -> Todo | None:
        row = self._conn.execute(
            f"SELECT {_TODO_COLUMNS} FROM todos WHERE id = ?", (todo_id,)
        ).fetchone()
        if row is None:
            return None
        return row_to_todo(row, self.load_tags([todo_id]).get(todo_id, ()))

    def update(
        self,
        todo_id: int,
        *,
        title: str | _Unset = UNSET,
        notes: str | None | _Unset = UNSET,
        due_date: str | None | _Unset = UNSET,
        priority: int | str | _Unset = UNSET,
    ) -> bool:
        """준 필드만 바꾼다. UNSET은 '건드리지 마라', None은 '비워라'."""
        assignments: list[str] = []
        params: list[object] = []
        if is_set(title):
            assignments.append("title = ?")
            params.append(normalize_title(title))
        if is_set(notes):
            assignments.append("notes = ?")
            params.append(_clean_notes(notes))
        if is_set(due_date):
            assignments.append("due_date = ?")
            params.append(normalize_due_date(due_date))
        if is_set(priority):
            assignments.append("priority = ?")
            params.append(normalize_priority(priority))
        if not assignments:
            return False
        params.append(todo_id)
        cursor = self._conn.execute(
            f"UPDATE todos SET {', '.join(assignments)} WHERE id = ?", params
        )
        return cursor.rowcount > 0

    def set_done(self, todo_id: int, done: bool) -> bool:
        """완료 표시를 바꾼다. completed_at·updated_at은 트리거가 알아서 채운다."""
        cursor = self._conn.execute(
            "UPDATE todos SET is_done = ? WHERE id = ?", (1 if done else 0, todo_id)
        )
        return cursor.rowcount > 0

    def delete(self, todo_id: int) -> bool:
        """할 일을 지운다. todo_tags 연결은 ON DELETE CASCADE가 정리한다."""
        cursor = self._conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        return cursor.rowcount > 0

    def replace_tags(self, todo_id: int, tag_ids: Sequence[int]) -> None:
        """이 할 일의 태그 연결을 주어진 목록으로 통째로 교체한다."""
        self._conn.execute("DELETE FROM todo_tags WHERE todo_id = ?", (todo_id,))
        unique_ids = list(dict.fromkeys(tag_ids))
        if unique_ids:
            self._conn.executemany(
                "INSERT INTO todo_tags (todo_id, tag_id) VALUES (?, ?)",
                [(todo_id, tag_id) for tag_id in unique_ids],
            )

    def load_tags(self, todo_ids: Sequence[int]) -> dict[int, tuple[Tag, ...]]:
        """여러 할 일의 태그를 쿼리 한 번으로 가져온다.

        할 일마다 태그를 따로 조회하면 목록 10개에 쿼리 11번(N+1)이 된다.
        여기서 한 번에 받아 파이썬에서 묶는다.

        바인딩 변수를 id 개수만큼 쓴다. SQLite의 상한은 32766개(3.32+ 기본값)라
        개인용 규모에서는 문제되지 않는다.
        """
        ids = list(dict.fromkeys(todo_ids))
        if not ids:
            return {}
        placeholders = ", ".join("?" * len(ids))
        rows = self._conn.execute(
            f"""
            SELECT tt.todo_id, g.id, g.name, g.color
              FROM todo_tags tt
              JOIN tags g ON g.id = tt.tag_id
             WHERE tt.todo_id IN ({placeholders})
             ORDER BY g.name COLLATE NOCASE ASC
            """,
            ids,
        ).fetchall()
        grouped: dict[int, list[Tag]] = {todo_id: [] for todo_id in ids}
        for row in rows:
            grouped[row["todo_id"]].append(row_to_tag(row))
        return {todo_id: tuple(tag_list) for todo_id, tag_list in grouped.items()}

    _ORDER_BY = (
        "ORDER BY is_done ASC, due_date IS NULL ASC, due_date ASC, priority ASC, id ASC"
    )

    def list(
        self,
        *,
        done: bool | None = None,
        tag: str | None = None,
        keyword: str | None = None,
        due_on_or_before: str | None = None,
        due_before: str | None = None,
        has_due: bool | None = None,
        priority: int | str | None = None,
    ) -> list[Todo]:
        """조건에 맞는 할 일을 정렬해 돌려준다. 태그도 함께 채운다.

        None인 필터는 '거르지 않음'을 뜻한다.
        정렬: 미완료 먼저 → 마감일 있는 것 먼저 → 임박한 순 → 우선순위 → 등록순.
        """
        where, params = _build_list_where(
            done=done,
            tag=tag,
            keyword=keyword,
            due_on_or_before=due_on_or_before,
            due_before=due_before,
            has_due=has_due,
            priority=priority,
        )
        rows = self._conn.execute(
            f"SELECT {_TODO_COLUMNS} FROM todos {where} {self._ORDER_BY}", params
        ).fetchall()
        tags_by_todo = self.load_tags([row["id"] for row in rows])
        return [row_to_todo(row, tags_by_todo.get(row["id"], ())) for row in rows]

    def count_all(self) -> int:
        return int(self._conn.execute("SELECT count(*) AS c FROM todos").fetchone()["c"])
