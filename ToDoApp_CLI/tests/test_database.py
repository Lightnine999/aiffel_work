"""커넥션 설정과 스키마 적용 테스트."""
from __future__ import annotations

import sqlite3

import pytest

from todoapp.database import connect, initialize, open_db


def test_외래키_검사가_켜져_있다(conn):
    # SQLite는 기본이 OFF다. 꺼져 있으면 CASCADE가 조용히 동작하지 않는다.
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_재귀_트리거가_꺼져_있다(conn):
    # 트리거 본문이 같은 표를 UPDATE하므로, 재귀가 켜지면 무한히 재발동한다.
    assert conn.execute("PRAGMA recursive_triggers").fetchone()[0] == 0


def test_행을_이름으로_꺼낼_수_있다(conn):
    row = conn.execute("SELECT 1 AS answer").fetchone()
    assert row["answer"] == 1


def test_스키마가_표_세_개를_만든다(conn):
    names = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert {"todos", "tags", "todo_tags"} <= names


def test_스키마가_뷰와_트리거를_만든다(conn):
    objects = {
        (r["type"], r["name"])
        for r in conn.execute(
            "SELECT type, name FROM sqlite_master WHERE type IN ('view','trigger')"
        )
    }
    assert ("view", "v_today_todos") in objects
    assert ("view", "v_todo_list") in objects
    assert ("trigger", "trg_todos_updated_at") in objects
    assert ("trigger", "trg_todos_completed_at") in objects


def test_initialize를_두_번_불러도_안전하다(conn):
    # 스키마가 전부 IF NOT EXISTS이므로 재실행이 깨지면 안 된다.
    initialize(conn)
    initialize(conn)
    assert conn.execute("SELECT count(*) AS c FROM todos").fetchone()["c"] == 0


def test_없는_상위_폴더를_자동으로_만든다(tmp_path):
    target = tmp_path / "없는폴더" / "todo.db"
    connection = connect(target)
    try:
        assert target.parent.is_dir()
    finally:
        connection.close()


def test_스키마_파일이_없으면_알려준다(conn, tmp_path):
    with pytest.raises(FileNotFoundError):
        initialize(conn, tmp_path / "없는스키마.sql")


def test_open_db는_빠져나갈_때_닫는다(db_path):
    with open_db(db_path) as connection:
        connection.execute("INSERT INTO todos (title) VALUES ('테스트')")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_open_db는_커밋한다(db_path):
    with open_db(db_path) as first:
        with first:
            first.execute("INSERT INTO todos (title) VALUES ('남아야 한다')")
    with open_db(db_path) as second:
        assert second.execute("SELECT count(*) AS c FROM todos").fetchone()["c"] == 1


def test_외래키_위반은_거부된다(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO todo_tags (todo_id, tag_id) VALUES (999, 999)")
