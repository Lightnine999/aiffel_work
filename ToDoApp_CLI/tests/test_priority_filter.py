"""우선순위 필터 — `todo.py list --priority high`.

CLAUDE.md 규칙대로 저장소 양쪽에 넣는다. 여기서 검증하는 것:
  SQLite   실제 WHERE 절이 걸러내는지
  Supabase 올바른 PostgREST 호출(eq)로 번역되는지 (가짜 클라이언트)
  service  이름('high')·숫자(1) 모두 받고 잘못된 값은 ValidationError
  CLI      --priority 플래그와 오류 종료코드
"""
from __future__ import annotations

import pytest

from todoapp.cli import main
from todoapp.models import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_NORMAL, ValidationError
from todoapp.repository import TodoRepository
from todoapp.service import TodoService
from todoapp.stores.supabase_store import SupabaseStore

from tests.test_supabase_store import FakeClient

FIXED_TODAY = "2026-09-04"


@pytest.fixture
def service(conn) -> TodoService:
    return TodoService(conn, today=lambda: FIXED_TODAY)


@pytest.fixture
def run(service):
    def _run(*argv, confirm=None):
        return main(list(argv), service=service, confirm=confirm or (lambda _: True))

    return _run


@pytest.fixture
def seeded(service):
    return {
        "높음": service.add("과제 제출", due=FIXED_TODAY, priority="high").id,
        "보통": service.add("설거지", due=FIXED_TODAY).id,
        "낮음": service.add("영화 보기", due=FIXED_TODAY, priority="low").id,
    }


# ---------------------------------------------------------------- SQLite


class TestRepositoryFilter:
    def test_높음만_돌려준다(self, conn, seeded):
        repo = TodoRepository(conn)
        assert [t.id for t in repo.list(priority=PRIORITY_HIGH)] == [seeded["높음"]]

    def test_지정하지_않으면_전부(self, conn, seeded):
        assert len(TodoRepository(conn).list()) == 3

    def test_이름으로도_받는다(self, conn, seeded):
        repo = TodoRepository(conn)
        assert [t.id for t in repo.list(priority="low")] == [seeded["낮음"]]

    def test_다른_필터와_함께_걸린다(self, conn, service, seeded):
        service.complete(seeded["높음"])
        repo = TodoRepository(conn)
        assert repo.list(priority=PRIORITY_HIGH, done=False) == []
        assert [t.id for t in repo.list(priority=PRIORITY_HIGH, done=True)] == [
            seeded["높음"]
        ]

    def test_알_수_없는_값은_거부한다(self, conn):
        with pytest.raises(ValidationError):
            TodoRepository(conn).list(priority="아주높음")


# ---------------------------------------------------------------- Supabase


class TestSupabaseRequestShape:
    def test_priority를_eq로_보낸다(self):
        client = FakeClient()
        SupabaseStore(client, user_id="uid-1").todos.list(priority=PRIORITY_HIGH)
        assert ("eq", ("priority", PRIORITY_HIGH), {}) in client.calls

    def test_이름은_숫자로_바꿔_보낸다(self):
        client = FakeClient()
        SupabaseStore(client, user_id="uid-1").todos.list(priority="high")
        assert ("eq", ("priority", PRIORITY_HIGH), {}) in client.calls

    def test_지정하지_않으면_priority_필터를_안_보낸다(self):
        client = FakeClient()
        SupabaseStore(client, user_id="uid-1").todos.list()
        assert not [c for c in client.calls if c[0] == "eq" and c[1][0] == "priority"]


# ---------------------------------------------------------------- 서비스


class TestServiceFilter:
    def test_범위와_함께_걸린다(self, service, seeded):
        found = service.list("today", priority="high")
        assert [t.id for t in found] == [seeded["높음"]]

    def test_숫자로도_받는다(self, service, seeded):
        assert [t.id for t in service.list(priority=PRIORITY_NORMAL)] == [
            seeded["보통"]
        ]

    def test_지정하지_않으면_전부(self, service, seeded):
        assert len(service.list()) == 3

    def test_알_수_없는_값은_ValidationError(self, service, seeded):
        with pytest.raises(ValidationError):
            service.list(priority="아주높음")


# ---------------------------------------------------------------- CLI


class TestListPriorityOption:
    def test_높음만_출력한다(self, run, seeded, capsys):
        assert run("list", "--priority", "high") == 0
        out = capsys.readouterr().out
        assert "과제 제출" in out
        assert "설거지" not in out
        assert "영화 보기" not in out

    def test_숫자로도_받는다(self, run, seeded, capsys):
        assert run("list", "--priority", "3") == 0
        assert "영화 보기" in capsys.readouterr().out

    def test_범위_플래그와_같이_쓴다(self, run, service, seeded, capsys):
        service.complete(seeded["높음"])
        assert run("list", "--active", "--priority", "high") == 0
        assert "할 일이 없습니다" in capsys.readouterr().out

    def test_잘못된_값은_사용자_오류로_끝낸다(self, run, seeded, capsys):
        assert run("list", "--priority", "아주높음") == 1
        assert "우선순위" in capsys.readouterr().err
