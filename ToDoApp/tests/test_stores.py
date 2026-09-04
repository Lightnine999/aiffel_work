"""저장소 이음새 테스트.

서비스가 저장소를 갈아끼울 수 있는 형태인지, 트랜잭션 경계가 실제로
동작하는지 확인한다. 저장소 구현별 동작은 각 구현의 테스트에서 본다.
"""
from __future__ import annotations

import sqlite3

import pytest

from todoapp.service import TodoService
from todoapp.stores import Store, build_store
from todoapp.stores.sqlite_store import SqliteStore


@pytest.fixture
def store(conn) -> SqliteStore:
    return SqliteStore(conn)


class TestProtocol:
    def test_SqliteStore가_Store_프로토콜을_만족한다(self, store):
        assert isinstance(store, Store)

    def test_필요한_속성이_모두_있다(self, store):
        for name in ("todos", "tags", "transaction"):
            assert hasattr(store, name), name


class TestTransaction:
    def test_성공하면_커밋된다(self, store, db_path):
        from todoapp.database import connect

        with store.transaction():
            store.todos.add("남아야 한다")
        other = connect(db_path)
        try:
            assert other.execute("SELECT count(*) AS c FROM todos").fetchone()["c"] == 1
        finally:
            other.close()

    def test_예외가_나면_롤백된다(self, store):
        with pytest.raises(RuntimeError):
            with store.transaction():
                store.todos.add("사라져야 한다")
                raise RuntimeError("중간에 실패")
        assert store.todos.list() == []

    def test_할_일과_태그_연결이_한_덩어리로_롤백된다(self, store):
        with pytest.raises(sqlite3.IntegrityError):
            with store.transaction():
                todo_id = store.todos.add("과제")
                store.todos.replace_tags(todo_id, [9999])  # 없는 태그 id
        assert store.todos.list() == []
        assert store.tags.list_all() == []


class TestServiceAcceptsBoth:
    def test_Store를_주면_동작한다(self, store):
        service = TodoService(store)
        todo = service.add("장보기", tags="집안일")
        assert [t.name for t in todo.tags] == ["집안일"]

    def test_커넥션을_주면_알아서_감싼다(self, conn):
        # 하위 호환: 기존 호출부는 TodoService(conn) 형태를 쓴다
        service = TodoService(conn)
        assert service.add("장보기").title == "장보기"

    def test_서비스가_repository를_직접_import하지_않는다(self):
        import pathlib

        source = pathlib.Path("todoapp/service.py").read_text(encoding="utf-8")
        assert "TodoRepository" not in source
        assert "TagRepository" not in source


class TestBuildStore:
    def test_sqlite를_만든다(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DB_PATH", str(tmp_path / "built.db"))
        monkeypatch.setattr("todoapp.config.load_dotenv", lambda *a, **k: None)
        built = build_store("sqlite")
        try:
            assert isinstance(built, SqliteStore)
            assert built.todos.count_all() == 0
        finally:
            built.close()

    def test_supabase는_토큰_없이는_거부한다(self):
        from todoapp.auth_flow import NotLoggedIn

        with pytest.raises(NotLoggedIn, match="로그인"):
            build_store("supabase")

    def test_알_수_없는_이름은_거부한다(self):
        with pytest.raises(ValueError, match="알 수 없는 STORAGE"):
            build_store("mysql")


class TestStorageConfig:
    def test_기본값은_sqlite다(self, monkeypatch):
        from todoapp.config import get_storage_backend

        monkeypatch.delenv("STORAGE", raising=False)
        monkeypatch.setattr("todoapp.config.load_dotenv", lambda *a, **k: None)
        assert get_storage_backend() == "sqlite"

    @pytest.mark.parametrize("value", ["supabase", "SUPABASE", "  sqlite  "])
    def test_대소문자와_공백을_다듬는다(self, monkeypatch, value):
        from todoapp.config import get_storage_backend

        monkeypatch.setenv("STORAGE", value)
        monkeypatch.setattr("todoapp.config.load_dotenv", lambda *a, **k: None)
        assert get_storage_backend() == value.strip().lower()

    def test_잘못된_값은_거부한다(self, monkeypatch):
        from todoapp.config import get_storage_backend

        monkeypatch.setenv("STORAGE", "mongodb")
        monkeypatch.setattr("todoapp.config.load_dotenv", lambda *a, **k: None)
        with pytest.raises(RuntimeError, match="STORAGE"):
            get_storage_backend()
