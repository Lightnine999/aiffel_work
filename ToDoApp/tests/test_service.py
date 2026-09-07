"""서비스 계층 테스트. 날짜는 고정 시계로 못 박는다."""
from __future__ import annotations

import pytest

from todoapp.models import PRIORITY_HIGH, ValidationError
from todoapp.service import TodoNotFound, TodoService

FIXED_TODAY = "2026-09-04"


@pytest.fixture
def service(conn) -> TodoService:
    return TodoService(conn, today=lambda: FIXED_TODAY)


@pytest.fixture
def seeded(service):
    """고정 날짜(2026-09-04) 기준 표본."""
    ids = {
        "지남": service.add("지난 과제", due="2026-09-01", priority="high", tags="공부").id,
        "오늘": service.add("오늘 발표", due=FIXED_TODAY, tags="공부,회사").id,
        "미래": service.add("장보기", due="2026-09-20", tags="집안일").id,
        "마감없음": service.add("책 읽기").id,
    }
    ids["완료"] = service.add("설거지", due="2026-09-01", tags="집안일").id
    service.complete(ids["완료"])
    return ids


class TestAdd:
    def test_할_일을_추가한다(self, service):
        todo = service.add("장보기")
        assert todo.id is not None
        assert todo.title == "장보기"
        assert todo.is_done is False

    def test_태그를_문자열로_받는다(self, service):
        todo = service.add("과제", tags="공부, 집안일")
        assert [t.name for t in todo.tags] == ["공부", "집안일"]

    def test_태그를_리스트로도_받는다(self, service):
        todo = service.add("과제", tags=["공부", "집안일"])
        assert [t.name for t in todo.tags] == ["공부", "집안일"]

    def test_없는_태그는_자동으로_만든다(self, service):
        service.add("과제", tags="새태그")
        assert [t.name for t in service.all_tags()] == ["새태그"]

    def test_있는_태그는_재사용한다(self, service):
        service.add("과제1", tags="공부")
        service.add("과제2", tags="공부")
        assert len(service.all_tags()) == 1

    def test_모든_필드를_받는다(self, service):
        todo = service.add(
            "장보기", notes="우유", due="2026-09-10", priority="high", tags="집안일"
        )
        assert todo.notes == "우유"
        assert todo.due_date == "2026-09-10"
        assert todo.priority == PRIORITY_HIGH
        assert [t.name for t in todo.tags] == ["집안일"]

    def test_검증_실패시_아무것도_저장되지_않는다(self, service):
        with pytest.raises(ValidationError):
            service.add("장보기", due="2026-02-31", tags="공부")
        # 롤백되어 할 일도 태그도 남지 않아야 한다
        assert service.list("all") == []
        assert service.all_tags() == []


class TestGetAndDelete:
    def test_없는_id를_읽으면_예외다(self, service):
        with pytest.raises(TodoNotFound) as exc:
            service.get(9999)
        assert exc.value.todo_id == 9999

    def test_삭제한다(self, service):
        todo = service.add("장보기")
        service.delete(todo.id)
        with pytest.raises(TodoNotFound):
            service.get(todo.id)

    def test_없는_id를_삭제하면_예외다(self, service):
        with pytest.raises(TodoNotFound):
            service.delete(9999)


class TestCompletion:
    def test_완료로_표시한다(self, service):
        todo = service.add("장보기")
        done = service.complete(todo.id)
        assert done.is_done is True
        assert done.completed_at is not None

    def test_완료를_되돌린다(self, service):
        todo = service.add("장보기")
        service.complete(todo.id)
        reopened = service.reopen(todo.id)
        assert reopened.is_done is False
        assert reopened.completed_at is None

    def test_토글은_상태를_뒤집는다(self, service):
        todo = service.add("장보기")
        assert service.toggle(todo.id).is_done is True
        assert service.toggle(todo.id).is_done is False

    def test_없는_id는_예외다(self, service):
        with pytest.raises(TodoNotFound):
            service.complete(9999)
        with pytest.raises(TodoNotFound):
            service.toggle(9999)


class TestEdit:
    def test_제목만_바꾼다(self, service):
        todo = service.add("장보기", notes="우유", tags="집안일")
        edited = service.edit(todo.id, title="장보기(수정)")
        assert edited.title == "장보기(수정)"
        assert edited.notes == "우유"
        assert [t.name for t in edited.tags] == ["집안일"]

    def test_마감일을_비운다(self, service):
        todo = service.add("장보기", due="2026-09-10")
        assert service.edit(todo.id, due=None).due_date is None

    def test_태그를_교체한다(self, service):
        todo = service.add("과제", tags="공부")
        edited = service.edit(todo.id, tags="집안일,운동")
        assert [t.name for t in edited.tags] == ["운동", "집안일"]

    def test_태그를_전부_뗀다(self, service):
        todo = service.add("과제", tags="공부")
        assert service.edit(todo.id, tags="").tags == ()

    def test_tags를_안_주면_태그는_그대로다(self, service):
        todo = service.add("과제", tags="공부")
        assert [t.name for t in service.edit(todo.id, title="새 제목").tags] == ["공부"]

    def test_없는_id는_예외다(self, service):
        with pytest.raises(TodoNotFound):
            service.edit(9999, title="없음")

    def test_아무것도_안_주면_그대로_돌려준다(self, service):
        todo = service.add("장보기")
        assert service.edit(todo.id) == todo

    def test_검증_실패시_태그도_바뀌지_않는다(self, service):
        todo = service.add("과제", tags="공부")
        with pytest.raises(ValidationError):
            service.edit(todo.id, due="2026-02-31", tags="집안일")
        assert [t.name for t in service.get(todo.id).tags] == ["공부"]


class TestListScopes:
    def test_all은_전부다(self, service, seeded):
        assert len(service.list("all")) == 5

    def test_active는_미완료만(self, service, seeded):
        assert len(service.list("active")) == 4

    def test_done은_완료만(self, service, seeded):
        assert [t.id for t in service.list("done")] == [seeded["완료"]]

    def test_today는_오늘까지_마감인_미완료다(self, service, seeded):
        assert {t.id for t in service.list("today")} == {seeded["지남"], seeded["오늘"]}

    def test_overdue는_이미_지난_미완료다(self, service, seeded):
        assert [t.id for t in service.list("overdue")] == [seeded["지남"]]

    def test_no_due는_마감일_없는_미완료다(self, service, seeded):
        assert [t.id for t in service.list("no-due")] == [seeded["마감없음"]]

    def test_태그_필터와_함께_쓸_수_있다(self, service, seeded):
        assert {t.id for t in service.list("active", tag="공부")} == {
            seeded["지남"],
            seeded["오늘"],
        }

    def test_키워드_필터와_함께_쓸_수_있다(self, service, seeded):
        assert [t.id for t in service.list("all", keyword="장보기")] == [seeded["미래"]]

    def test_알_수_없는_scope는_거부한다(self, service):
        with pytest.raises(ValidationError):
            service.list("이상한값")

    def test_기본_scope는_all이다(self, service, seeded):
        assert len(service.list()) == 5


class TestSummary:
    def test_개수를_집계한다(self, service, seeded):
        assert service.summary() == {
            "total": 5,
            "active": 4,
            "done": 1,
            "today": 2,
            "overdue": 1,
        }

    def test_빈_DB의_집계는_전부_0이다(self, service):
        assert service.summary() == {
            "total": 0,
            "active": 0,
            "done": 0,
            "today": 0,
            "overdue": 0,
        }


class TestClockInjection:
    def test_today_메서드가_주입된_시계를_돌려준다(self, service):
        assert service.today() == FIXED_TODAY

    def test_시계를_바꾸면_today_결과가_바뀐다(self, conn):
        early = TodoService(conn, today=lambda: "2026-09-04")
        todo = early.add("발표", due="2026-09-10")
        assert early.list("today") == []
        late = TodoService(conn, today=lambda: "2026-09-11")
        assert [t.id for t in late.list("today")] == [todo.id]

    def test_기본_시계는_실제_오늘이다(self, conn):
        from datetime import date

        assert TodoService(conn).today() == date.today().isoformat()
