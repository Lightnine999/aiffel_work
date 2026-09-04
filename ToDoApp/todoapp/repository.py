"""SQL 전담 계층.

앱 안에서 SQL 문자열이 존재하는 곳은 이 파일과 db/schema.sql 뿐이다.
상위 계층(service·cli·web)은 SQL을 모른다.
"""

from __future__ import annotations

import sqlite3

from todoapp.models import (
    DEFAULT_TAG_COLOR,
    Tag,
    normalize_color,
    normalize_tag_name,
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
