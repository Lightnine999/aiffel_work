"""태그 리포지토리 테스트."""
from __future__ import annotations

import pytest

from todoapp.models import Tag, ValidationError
from todoapp.repository import TagRepository


@pytest.fixture
def tags(conn) -> TagRepository:
    return TagRepository(conn)


def test_새_태그를_만든다(tags):
    tag = tags.upsert("공부")
    assert isinstance(tag, Tag)
    assert tag.id is not None
    assert tag.name == "공부"
    assert tag.color == "#888880"


def test_색상을_지정할_수_있다(tags):
    tag = tags.upsert("공부", "#534ab7")
    assert tag.color == "#534AB7"  # 대문자로 정규화된다


def test_같은_이름을_다시_넣으면_같은_행을_돌려준다(tags):
    first = tags.upsert("공부")
    second = tags.upsert("공부")
    assert first.id == second.id
    assert len(tags.list_all()) == 1


def test_대소문자만_다른_이름도_같은_행이다(tags):
    first = tags.upsert("Study")
    second = tags.upsert("study")
    assert first.id == second.id
    # 처음 저장된 표기를 유지한다
    assert second.name == "Study"
    assert len(tags.list_all()) == 1


def test_다시_넣을_때_색상만_바꿀_수_있다(tags):
    original = tags.upsert("공부", "#534AB7")
    updated = tags.upsert("공부", "#1D9E75")
    assert updated.id == original.id
    assert updated.color == "#1D9E75"


def test_색상을_생략하면_기존_색상을_지킨다(tags):
    tags.upsert("공부", "#534AB7")
    kept = tags.upsert("공부")
    assert kept.color == "#534AB7"


def test_앞뒤_공백은_제거된다(tags):
    assert tags.upsert("  공부  ").name == "공부"


def test_빈_이름은_거부한다(tags):
    with pytest.raises(ValidationError):
        tags.upsert("   ")


def test_잘못된_색상은_거부한다(tags):
    with pytest.raises(ValidationError):
        tags.upsert("공부", "red")


def test_이름으로_찾는다_대소문자_무시(tags):
    created = tags.upsert("Study")
    assert tags.get_by_name("STUDY").id == created.id


def test_없는_이름은_None이다(tags):
    assert tags.get_by_name("없는태그") is None


def test_id로_찾는다(tags):
    created = tags.upsert("공부")
    assert tags.get(created.id).name == "공부"
    assert tags.get(9999) is None


def test_전체_목록은_이름순이다(tags):
    tags.upsert("집안일")
    tags.upsert("공부")
    tags.upsert("운동")
    assert [t.name for t in tags.list_all()] == ["공부", "운동", "집안일"]


def test_아무_할_일에도_안_붙은_태그를_지운다(conn, tags):
    used = tags.upsert("공부")
    tags.upsert("고아태그")
    conn.execute("INSERT INTO todos (title) VALUES ('할 일')")
    todo_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.execute("INSERT INTO todo_tags (todo_id, tag_id) VALUES (?, ?)", (todo_id, used.id))
    assert tags.delete_unused() == 1
    assert [t.name for t in tags.list_all()] == ["공부"]
