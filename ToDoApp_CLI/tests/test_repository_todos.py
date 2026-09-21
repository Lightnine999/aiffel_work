"""할 일 리포지토리 CRUD·태그 연결 테스트."""
from __future__ import annotations

import sqlite3

import pytest

from todoapp.models import PRIORITY_HIGH, PRIORITY_NORMAL, ValidationError
from todoapp.repository import UNSET, TagRepository, TodoRepository, is_set


@pytest.fixture
def todos(conn) -> TodoRepository:
    return TodoRepository(conn)


@pytest.fixture
def tags(conn) -> TagRepository:
    return TagRepository(conn)


class TestUnsetSentinel:
    def test_UNSET은_주어지지_않은_값이다(self):
        assert is_set(UNSET) is False

    def test_None도_주어진_값이다(self):
        # '비워라'(None)와 '건드리지 마라'(UNSET)는 다른 뜻이다.
        assert is_set(None) is True
        assert is_set("") is True

    def test_UNSET은_싱글턴이다(self):
        from todoapp.repository import _Unset

        assert _Unset() is UNSET


class TestAdd:
    def test_할_일을_추가하고_id를_돌려준다(self, todos):
        todo_id = todos.add("장보기")
        assert isinstance(todo_id, int) and todo_id > 0

    def test_추가한_내용을_그대로_읽는다(self, todos):
        todo_id = todos.add("장보기", notes="우유, 계란", due_date="2026-09-10", priority="high")
        todo = todos.get(todo_id)
        assert todo.title == "장보기"
        assert todo.notes == "우유, 계란"
        assert todo.due_date == "2026-09-10"
        assert todo.priority == PRIORITY_HIGH
        assert todo.is_done is False
        assert todo.completed_at is None
        assert todo.tags == ()

    def test_생성_시각이_기록된다(self, todos):
        todo = todos.get(todos.add("장보기"))
        assert todo.created_at is not None
        assert todo.updated_at is not None

    def test_기본_우선순위는_보통이다(self, todos):
        assert todos.get(todos.add("장보기")).priority == PRIORITY_NORMAL

    def test_공백만_있는_메모는_None이_된다(self, todos):
        assert todos.get(todos.add("장보기", notes="   ")).notes is None

    def test_제목_검증이_적용된다(self, todos):
        with pytest.raises(ValidationError):
            todos.add("   ")

    def test_마감일_검증이_적용된다(self, todos):
        with pytest.raises(ValidationError):
            todos.add("장보기", due_date="2026-02-31")

    def test_없는_id는_None이다(self, todos):
        assert todos.get(9999) is None


class TestSetDone:
    def test_완료로_표시한다(self, todos):
        todo_id = todos.add("장보기")
        assert todos.set_done(todo_id, True) is True
        todo = todos.get(todo_id)
        assert todo.is_done is True
        assert todo.completed_at is not None  # 트리거가 기록한다

    def test_완료를_되돌리면_완료시각이_지워진다(self, todos):
        todo_id = todos.add("장보기")
        todos.set_done(todo_id, True)
        todos.set_done(todo_id, False)
        todo = todos.get(todo_id)
        assert todo.is_done is False
        assert todo.completed_at is None

    def test_없는_id는_False다(self, todos):
        assert todos.set_done(9999, True) is False


class TestUpdate:
    def test_제목을_바꾼다(self, todos):
        todo_id = todos.add("장보기")
        assert todos.update(todo_id, title="장보기(수정)") is True
        assert todos.get(todo_id).title == "장보기(수정)"

    def test_안_넘긴_필드는_그대로다(self, todos):
        todo_id = todos.add("장보기", notes="우유", due_date="2026-09-10")
        todos.update(todo_id, title="새 제목")
        todo = todos.get(todo_id)
        assert todo.notes == "우유"
        assert todo.due_date == "2026-09-10"

    def test_None을_명시하면_지워진다(self, todos):
        todo_id = todos.add("장보기", notes="우유", due_date="2026-09-10")
        todos.update(todo_id, notes=None, due_date=None)
        todo = todos.get(todo_id)
        assert todo.notes is None
        assert todo.due_date is None

    def test_아무_필드도_안_주면_아무것도_안_한다(self, todos):
        todo_id = todos.add("장보기")
        before = todos.get(todo_id)
        assert todos.update(todo_id) is False
        assert todos.get(todo_id) == before

    def test_없는_id는_False다(self, todos):
        assert todos.update(9999, title="없음") is False

    def test_검증이_적용된다(self, todos):
        todo_id = todos.add("장보기")
        with pytest.raises(ValidationError):
            todos.update(todo_id, due_date="2026/09/10")


class TestDelete:
    def test_삭제하면_사라진다(self, todos):
        todo_id = todos.add("장보기")
        assert todos.delete(todo_id) is True
        assert todos.get(todo_id) is None

    def test_없는_id는_False다(self, todos):
        assert todos.delete(9999) is False

    def test_삭제하면_태그_연결도_함께_사라진다(self, conn, todos, tags):
        todo_id = todos.add("장보기")
        tag = tags.upsert("집안일")
        todos.replace_tags(todo_id, [tag.id])
        todos.delete(todo_id)
        remaining = conn.execute("SELECT count(*) AS c FROM todo_tags").fetchone()["c"]
        assert remaining == 0
        # 태그 사전 자체는 남는다
        assert tags.get(tag.id) is not None


class TestTags:
    def test_태그를_붙인다(self, todos, tags):
        todo_id = todos.add("과제")
        study = tags.upsert("공부")
        todos.replace_tags(todo_id, [study.id])
        assert [t.name for t in todos.get(todo_id).tags] == ["공부"]

    def test_태그를_여러_개_붙이면_이름순으로_나온다(self, todos, tags):
        todo_id = todos.add("과제")
        ids = [tags.upsert(n).id for n in ("집안일", "공부", "운동")]
        todos.replace_tags(todo_id, ids)
        assert [t.name for t in todos.get(todo_id).tags] == ["공부", "운동", "집안일"]

    def test_replace_tags는_기존_연결을_대체한다(self, todos, tags):
        todo_id = todos.add("과제")
        study, chore = tags.upsert("공부"), tags.upsert("집안일")
        todos.replace_tags(todo_id, [study.id, chore.id])
        todos.replace_tags(todo_id, [chore.id])
        assert [t.name for t in todos.get(todo_id).tags] == ["집안일"]

    def test_빈_목록을_주면_전부_떼어낸다(self, todos, tags):
        todo_id = todos.add("과제")
        todos.replace_tags(todo_id, [tags.upsert("공부").id])
        todos.replace_tags(todo_id, [])
        assert todos.get(todo_id).tags == ()

    def test_같은_태그를_두_번_주어도_한_번만_붙는다(self, todos, tags):
        todo_id = todos.add("과제")
        study = tags.upsert("공부")
        todos.replace_tags(todo_id, [study.id, study.id])
        assert len(todos.get(todo_id).tags) == 1

    def test_없는_태그_id는_거부된다(self, todos):
        todo_id = todos.add("과제")
        with pytest.raises(sqlite3.IntegrityError):
            todos.replace_tags(todo_id, [9999])

    def test_load_tags는_쿼리_한_번으로_여러_할_일의_태그를_가져온다(self, todos, tags):
        study, chore = tags.upsert("공부"), tags.upsert("집안일")
        first = todos.add("과제")
        second = todos.add("청소")
        third = todos.add("태그없음")
        todos.replace_tags(first, [study.id])
        todos.replace_tags(second, [chore.id, study.id])
        loaded = todos.load_tags([first, second, third])
        assert [t.name for t in loaded[first]] == ["공부"]
        assert [t.name for t in loaded[second]] == ["공부", "집안일"]
        assert loaded[third] == ()

    def test_load_tags에_빈_목록을_주면_빈_사전이다(self, todos):
        assert todos.load_tags([]) == {}
