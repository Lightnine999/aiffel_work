"""SupabaseStore 테스트. 가짜 클라이언트로 '어떤 요청을 만드는지'를 본다.

실제 네트워크 왕복은 tests/test_supabase_integration.py 가 담당한다.
여기서 검증하는 것: 필터가 올바른 PostgREST 호출로 번역되는지, 와일드카드가
이스케이프되는지, 원자성이 필요한 작업이 RPC로 가는지.
"""
from __future__ import annotations

import pytest

from todoapp.models import PRIORITY_HIGH, ValidationError
from todoapp.stores.supabase_store import (
    SupabaseStore,
    escape_postgrest_pattern,
)


# ---------------------------------------------------------------- 가짜 클라이언트


class FakeQuery:
    """쿼리 빌더 흉내. 호출된 메서드와 인자를 순서대로 기록한다."""

    def __init__(self, recorder: list, rows: list):
        self._recorder = recorder
        self._rows = rows

    def _record(self, name, *args, **kwargs):
        self._recorder.append((name, args, kwargs))
        return self

    def __getattr__(self, name):
        def call(*args, **kwargs):
            return self._record(name, *args, **kwargs)

        return call

    def execute(self):
        self._recorder.append(("execute", (), {}))
        return type("Result", (), {"data": self._rows, "count": len(self._rows)})()


class FakeClient:
    def __init__(self, rows=None, rpc_result=None):
        self.calls: list = []
        self.rpc_calls: list = []
        self._rows = rows if rows is not None else []
        self._rpc_result = rpc_result

    def table(self, name):
        self.calls.append(("table", (name,), {}))
        return FakeQuery(self.calls, self._rows)

    def rpc(self, fn, params=None):
        self.rpc_calls.append((fn, params or {}))
        result = self._rpc_result
        return type(
            "RpcQuery",
            (),
            {"execute": lambda self_: type("R", (), {"data": result})()},
        )()

    def method_names(self) -> list[str]:
        return [c[0] for c in self.calls]

    def args_for(self, method: str) -> list[tuple]:
        return [c[1] for c in self.calls if c[0] == method]


@pytest.fixture
def client():
    return FakeClient()


def store_for(client) -> SupabaseStore:
    return SupabaseStore(client, user_id="uid-1")


# ---------------------------------------------------------------- 와일드카드


class TestEscapePattern:
    def test_보통_글자는_그대로(self):
        assert escape_postgrest_pattern("장보기") == "장보기"

    def test_별표는_이스케이프한다(self):
        # PostgREST의 ilike 패턴에서 *는 '아무 문자열'을 뜻한다.
        # 그대로 두면 사용자가 '*'를 검색할 때 전부 일치해 버린다.
        assert escape_postgrest_pattern("100*") == r"100\*"

    def test_쉼표는_이스케이프한다(self):
        # or_() 필터는 쉼표로 조건을 나눈다. 그대로 두면 필터가 쪼개진다.
        assert escape_postgrest_pattern("a,b") == r"a\,b"

    def test_괄호와_점도_이스케이프한다(self):
        assert escape_postgrest_pattern("a(b).c") == r"a\(b\)\.c"

    def test_역슬래시를_가장_먼저_바꾼다(self):
        # 나중에 바꾸면 방금 붙인 이스케이프 문자까지 이중으로 바뀐다
        assert escape_postgrest_pattern("a\\b") == r"a\\b"

    def test_퍼센트는_건드리지_않는다(self):
        # PostgREST에서 %는 특별하지 않다 (SQLite와 다르다)
        assert escape_postgrest_pattern("100%") == "100%"


# ---------------------------------------------------------------- 조회


class TestList:
    def test_기본_조회는_정렬을_건다(self, client):
        store_for(client).todos.list()
        assert client.method_names().count("order") >= 3

    def test_완료_여부로_거른다(self, client):
        store_for(client).todos.list(done=False)
        assert ("is_done", False) in [a for a in client.args_for("eq")]

    def test_마감일_이하로_거른다(self, client):
        store_for(client).todos.list(due_on_or_before="2026-09-04")
        assert ("due_date", "2026-09-04") in client.args_for("lte")

    def test_마감일_미만으로_거른다(self, client):
        store_for(client).todos.list(due_before="2026-09-04")
        assert ("due_date", "2026-09-04") in client.args_for("lt")

    def test_마감일_유무로_거른다(self, client):
        store_for(client).todos.list(has_due=False)
        assert ("due_date", "null") in client.args_for("is_")

    def test_키워드는_제목과_메모_둘_다_본다(self, client):
        store_for(client).todos.list(keyword="장보")
        (filter_string,) = client.args_for("or_")[0]
        assert "title.ilike" in filter_string
        assert "notes.ilike" in filter_string

    def test_키워드의_별표가_이스케이프된다(self, client):
        store_for(client).todos.list(keyword="100*")
        (filter_string,) = client.args_for("or_")[0]
        assert r"100\*" in filter_string

    def test_키워드의_쉼표가_이스케이프된다(self, client):
        # 이스케이프하지 않으면 or_ 필터가 쪼개져 엉뚱한 조건이 된다
        store_for(client).todos.list(keyword="우유,계란")
        (filter_string,) = client.args_for("or_")[0]
        assert r"우유\,계란" in filter_string

    def test_공백만_있는_키워드는_거르지_않는다(self, client):
        store_for(client).todos.list(keyword="   ")
        assert client.args_for("or_") == []

    def test_잘못된_마감일은_거부한다(self, client):
        with pytest.raises(ValidationError):
            store_for(client).todos.list(due_on_or_before="2026-02-31")

    def test_태그_필터는_이름을_정규화한다(self, client):
        store_for(client).todos.list(tag="  공부  ")
        # 태그는 임베드 조회로 처리한다
        assert any("todo_tags" in str(a) for a in client.args_for("select"))


class TestRowMapping:
    def test_Postgres_불리언을_그대로_받는다(self):
        client = FakeClient(rows=[{
            "id": 1, "title": "장보기", "notes": None,
            "is_done": True, "due_date": "2026-09-10", "priority": 1,
            "created_at": "2026-09-04T10:00:00+00:00",
            "updated_at": "2026-09-04T10:00:00+00:00",
            "completed_at": "2026-09-04T11:00:00+00:00",
            "todo_tags": [],
        }])
        todo = store_for(client).todos.list()[0]
        assert todo.is_done is True
        assert todo.priority == PRIORITY_HIGH
        assert todo.due_date == "2026-09-10"

    def test_임베드된_태그를_이름순으로_붙인다(self):
        client = FakeClient(rows=[{
            "id": 1, "title": "과제", "notes": None, "is_done": False,
            "due_date": None, "priority": 2,
            "created_at": None, "updated_at": None, "completed_at": None,
            "todo_tags": [
                {"tags": {"id": 9, "name": "집안일", "color": "#111111"}},
                {"tags": {"id": 3, "name": "공부", "color": "#222222"}},
            ],
        }])
        todo = store_for(client).todos.list()[0]
        assert [t.name for t in todo.tags] == ["공부", "집안일"]


# ---------------------------------------------------------------- 원자성


class TestAtomicity:
    def test_추가는_RPC로_한_번에_보낸다(self):
        # PostgREST에는 클라이언트 트랜잭션이 없다. 할 일 insert와 태그 연결을
        # 따로 보내면 중간에 실패했을 때 반쯤 만들어진 상태가 남는다.
        client = FakeClient(rpc_result=42)
        new_id = store_for(client).todos.add(
            "장보기", due_date="2026-09-10", priority="high", tags=("공부", "집안일")
        )
        assert new_id == 42
        (fn, params) = client.rpc_calls[0]
        assert fn == "create_todo_with_tags"
        assert params["p_title"] == "장보기"
        assert params["p_due_date"] == "2026-09-10"
        assert params["p_priority"] == PRIORITY_HIGH
        assert params["p_tags"] == ["공부", "집안일"]

    def test_추가도_입력_검증을_거친다(self):
        client = FakeClient(rpc_result=1)
        with pytest.raises(ValidationError):
            store_for(client).todos.add("장보기", due_date="2026/09/10")
        assert client.rpc_calls == []  # 검증 실패 시 요청을 보내지 않는다

    def test_태그_교체도_RPC로_보낸다(self):
        client = FakeClient(rpc_result=None)
        store_for(client).todos.set_tags(1, ("공부",))
        (fn, params) = client.rpc_calls[0]
        assert fn == "set_todo_tags"
        assert params == {"p_todo_id": 1, "p_tags": ["공부"]}

    def test_transaction은_no_op이고_예외를_막지_않는다(self, client):
        store = store_for(client)
        with pytest.raises(RuntimeError):
            with store.transaction():
                raise RuntimeError("그대로 올라와야 한다")


class TestNoUserIdInWrites:
    def test_user_id를_직접_넣지_않는다(self):
        """user_id는 DB의 default auth.uid()가 채운다.

        앱이 직접 넣으면 남의 id를 넣으려는 시도가 가능해지고(정책이 막지만),
        무엇보다 '누구인지'의 출처가 두 곳으로 갈라진다.
        """
        import pathlib

        source = pathlib.Path("todoapp/stores/supabase_store.py").read_text(
            encoding="utf-8"
        )
        assert '"user_id"' not in source
        assert "'user_id'" not in source


class TestProtocolConformance:
    def test_SupabaseStore가_Store_프로토콜을_만족한다(self, client):
        from todoapp.stores import Store

        assert isinstance(store_for(client), Store)

    def test_두_저장소가_같은_복합_연산을_제공한다(self, client, conn):
        """이음새가 제대로 그어졌는지 확인한다.

        두 구현의 공개 표면이 어긋나면 STORAGE를 바꿨을 때 터진다.
        """
        from todoapp.stores.sqlite_store import SqliteStore

        supa = store_for(client)
        lite = SqliteStore(conn)
        for name in ("create_todo", "set_tags", "transaction", "todos", "tags"):
            assert hasattr(supa, name), f"SupabaseStore에 {name} 없음"
            assert hasattr(lite, name), f"SqliteStore에 {name} 없음"
        for name in ("get", "list", "update", "set_done", "delete", "count_all"):
            assert hasattr(supa.todos, name), f"SupabaseTodoStore에 {name} 없음"
            assert hasattr(lite.todos, name), f"TodoRepository에 {name} 없음"
        for name in ("upsert", "get", "get_by_name", "list_all"):
            assert hasattr(supa.tags, name), f"SupabaseTagStore에 {name} 없음"
            assert hasattr(lite.tags, name), f"TagRepository에 {name} 없음"

    def test_서비스가_두_저장소_모두와_동작한다(self, client, conn):
        """서비스는 어느 저장소든 같은 방식으로 부른다."""
        from todoapp.service import TodoService
        from todoapp.stores.sqlite_store import SqliteStore

        client._rpc_result = 7
        for store in (store_for(client), SqliteStore(conn)):
            service = TodoService(store, today=lambda: "2026-09-04")
            assert callable(service.add)
            assert callable(service.list)


class TestLayerBoundary:
    def test_화면_계층이_supabase를_모른다(self):
        """저장소 교체가 화면까지 새면 이음새를 잘못 그은 것이다."""
        import pathlib

        targets = [pathlib.Path("todoapp/cli.py")] + list(
            pathlib.Path("todoapp/web").rglob("*.py")
        )
        for path in targets:
            source = path.read_text(encoding="utf-8")
            assert "supabase_store" not in source, path
            assert "from supabase" not in source, path
            assert "import supabase" not in source, path

    def test_서비스가_저장소_구현을_모른다(self):
        import pathlib

        source = pathlib.Path("todoapp/service.py").read_text(encoding="utf-8")
        for forbidden in ("SqliteStore", "SupabaseStore", "supabase", "TodoRepository"):
            assert forbidden not in source, forbidden

    def test_supabase_store가_user_id를_직접_쓰지_않는다(self):
        """user_id는 DB의 default auth.uid()가 채운다."""
        import pathlib

        source = pathlib.Path("todoapp/stores/supabase_store.py").read_text(
            encoding="utf-8"
        )
        assert '"user_id":' not in source
