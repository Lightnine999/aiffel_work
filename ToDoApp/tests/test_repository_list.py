"""필터 조회와 스키마 뷰 정합성 테스트."""
from __future__ import annotations

import pytest

from todoapp.repository import TagRepository, TodoRepository


@pytest.fixture
def todos(conn) -> TodoRepository:
    return TodoRepository(conn)


@pytest.fixture
def tags(conn) -> TagRepository:
    return TagRepository(conn)


@pytest.fixture
def sample(conn, todos, tags):
    """고정된 표본. 날짜는 DB의 '오늘'을 기준으로 상대 계산한다."""
    today = conn.execute("SELECT date('now','localtime') AS d").fetchone()["d"]
    yesterday = conn.execute("SELECT date('now','localtime','-1 day') AS d").fetchone()["d"]
    next_week = conn.execute("SELECT date('now','localtime','+7 day') AS d").fetchone()["d"]

    study = tags.upsert("공부")
    chore = tags.upsert("집안일")

    ids = {
        "지난것": todos.add("지난 과제", due_date=yesterday, priority="high"),
        "오늘것": todos.add("오늘 발표", due_date=today, priority="normal"),
        "다음주": todos.add("장보기", due_date=next_week),
        "마감없음": todos.add("책 읽기"),
        "완료된것": todos.add("설거지", due_date=yesterday),
    }
    todos.replace_tags(ids["지난것"], [study.id])
    todos.replace_tags(ids["오늘것"], [study.id, chore.id])
    todos.replace_tags(ids["완료된것"], [chore.id])
    todos.set_done(ids["완료된것"], True)
    return {"ids": ids, "today": today, "yesterday": yesterday, "next_week": next_week}


class TestOrdering:
    def test_미완료가_먼저_나온다(self, todos, sample):
        result = todos.list()
        assert result[-1].id == sample["ids"]["완료된것"]

    def test_마감일이_임박한_순서다(self, todos, sample):
        active = [t.id for t in todos.list(done=False)]
        assert active == [
            sample["ids"]["지난것"],
            sample["ids"]["오늘것"],
            sample["ids"]["다음주"],
            sample["ids"]["마감없음"],  # 마감일 없는 것은 뒤로
        ]

    def test_마감일이_같으면_우선순위로_가른다(self, todos, sample):
        low = todos.add("낮음", due_date=sample["today"], priority="low")
        high = todos.add("높음", due_date=sample["today"], priority="high")
        same_day = [
            t.id for t in todos.list(done=False, due_on_or_before=sample["today"])
            if t.due_date == sample["today"]
        ]
        assert same_day.index(high) < same_day.index(low)


class TestFilters:
    def test_전체를_돌려준다(self, todos, sample):
        assert len(todos.list()) == 5

    def test_미완료만(self, todos, sample):
        assert all(not t.is_done for t in todos.list(done=False))
        assert len(todos.list(done=False)) == 4

    def test_완료만(self, todos, sample):
        result = todos.list(done=True)
        assert [t.id for t in result] == [sample["ids"]["완료된것"]]

    def test_태그로_거른다(self, todos, sample):
        result = todos.list(tag="공부")
        assert {t.id for t in result} == {sample["ids"]["지난것"], sample["ids"]["오늘것"]}

    def test_태그_필터는_대소문자를_무시한다(self, todos, tags):
        todo_id = todos.add("영어 공부")
        todos.replace_tags(todo_id, [tags.upsert("Study").id])
        assert [t.id for t in todos.list(tag="STUDY")] == [todo_id]

    def test_태그로_걸러도_중복_행이_생기지_않는다(self, todos, sample):
        # 태그 2개가 붙은 할 일이 JOIN 때문에 두 번 나오면 안 된다.
        result = todos.list(tag="집안일")
        assert len(result) == len({t.id for t in result})

    def test_없는_태그는_빈_목록이다(self, todos, sample):
        assert todos.list(tag="없는태그") == []

    def test_키워드로_제목을_찾는다(self, todos, sample):
        assert [t.id for t in todos.list(keyword="장보기")] == [sample["ids"]["다음주"]]

    def test_키워드로_메모도_찾는다(self, todos):
        todo_id = todos.add("병원", notes="치과 예약 확인")
        assert [t.id for t in todos.list(keyword="치과")] == [todo_id]

    def test_키워드의_와일드카드는_글자로_취급한다(self, todos):
        # LIKE의 %와 _를 escape하지 않으면 '%'가 '전부 일치'가 되어 버린다.
        todos.add("보고서 100% 완성")
        todos.add("전혀 다른 할 일")
        # '100%'를 글자 그대로 찾는다
        assert len(todos.list(keyword="100%")) == 1
        # '%'는 '아무 문자열'이 아니라 문자 '%'를 품은 것만 (표본에 1건)
        assert len(todos.list(keyword="%")) == 1
        # '_'는 '아무 한 글자'가 아니라 문자 '_'를 품은 것만 (표본에 0건)
        assert len(todos.list(keyword="_")) == 0

    def test_역슬래시를_검색해도_깨지지_않는다(self, todos):
        todos.add(r"경로 C:\temp 확인")
        assert len(todos.list(keyword=r"C:\temp")) == 1

    def test_공백만_있는_키워드는_거르지_않는다(self, todos, sample):
        assert len(todos.list(keyword="   ")) == 5

    def test_마감일_이하로_거른다(self, todos, sample):
        result = todos.list(done=False, due_on_or_before=sample["today"])
        assert {t.id for t in result} == {sample["ids"]["지난것"], sample["ids"]["오늘것"]}

    def test_마감일_미만으로_거른다(self, todos, sample):
        result = todos.list(done=False, due_before=sample["today"])
        assert {t.id for t in result} == {sample["ids"]["지난것"]}

    def test_마감일_유무로_거른다(self, todos, sample):
        assert [t.id for t in todos.list(has_due=False)] == [sample["ids"]["마감없음"]]
        assert sample["ids"]["마감없음"] not in {t.id for t in todos.list(has_due=True)}

    def test_필터를_겹쳐_쓸_수_있다(self, todos, sample):
        result = todos.list(done=False, tag="공부", due_on_or_before=sample["today"])
        assert {t.id for t in result} == {sample["ids"]["지난것"], sample["ids"]["오늘것"]}

    def test_목록의_태그가_함께_채워진다(self, todos, sample):
        by_id = {t.id: t for t in todos.list()}
        assert [g.name for g in by_id[sample["ids"]["오늘것"]].tags] == ["공부", "집안일"]
        assert by_id[sample["ids"]["마감없음"]].tags == ()

    def test_전체_개수를_센다(self, todos, sample):
        assert todos.count_all() == 5

    def test_빈_DB는_빈_목록이다(self, todos):
        assert todos.list() == []
        assert todos.count_all() == 0


class TestViewConsistency:
    """schema.sql의 뷰와 리포지토리 쿼리가 갈라지지 않는지 검사한다."""

    def test_v_todo_list와_list가_같은_순서를_준다(self, conn, todos, sample):
        view_ids = [r["id"] for r in conn.execute("SELECT id FROM v_todo_list")]
        repo_ids = [t.id for t in todos.list()]
        assert view_ids == repo_ids

    def test_v_todo_list의_태그_문자열이_리포지토리와_일치한다(self, conn, todos, sample):
        view = {
            r["id"]: r["tag_names"]
            for r in conn.execute("SELECT id, tag_names FROM v_todo_list")
        }
        for todo in todos.list():
            expected = ", ".join(g.name for g in todo.tags) or None
            assert view[todo.id] == expected

    def test_v_today_todos와_리포지토리가_일치한다(self, conn, todos, sample):
        view_ids = [r["id"] for r in conn.execute("SELECT id FROM v_today_todos")]
        repo_ids = [
            t.id
            for t in todos.list(
                done=False, due_on_or_before=sample["today"], has_due=True
            )
        ]
        assert view_ids == repo_ids
