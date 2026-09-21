"""CLI 테스트. subprocess 없이 main()을 직접 부른다."""
from __future__ import annotations

import pytest

from todoapp.cli import display_width, format_table, main, resolve_due_input
from todoapp.models import ValidationError
from todoapp.service import TodoService

FIXED_TODAY = "2026-09-04"


@pytest.fixture
def service(conn) -> TodoService:
    return TodoService(conn, today=lambda: FIXED_TODAY)


@pytest.fixture
def run(service):
    """CLI를 돌리고 종료 코드를 돌려주는 도우미."""

    def _run(*argv, confirm=None):
        return main(list(argv), service=service, confirm=confirm or (lambda _: True))

    return _run


class TestResolveDueInput:
    def test_ISO_날짜는_그대로(self):
        assert resolve_due_input("2026-09-10", FIXED_TODAY) == "2026-09-10"

    @pytest.mark.parametrize("word", ["today", "오늘", "TODAY"])
    def test_오늘(self, word):
        assert resolve_due_input(word, FIXED_TODAY) == FIXED_TODAY

    @pytest.mark.parametrize("word", ["tomorrow", "내일"])
    def test_내일(self, word):
        assert resolve_due_input(word, FIXED_TODAY) == "2026-09-05"

    def test_상대_일수(self):
        assert resolve_due_input("+7d", FIXED_TODAY) == "2026-09-11"
        assert resolve_due_input("-1d", FIXED_TODAY) == "2026-09-03"

    def test_달을_넘어가는_상대_일수(self):
        assert resolve_due_input("+30d", FIXED_TODAY) == "2026-10-04"

    @pytest.mark.parametrize("word", ["", "none", "없음", "   "])
    def test_비우기(self, word):
        assert resolve_due_input(word, FIXED_TODAY) is None

    def test_안_준_경우도_None(self):
        assert resolve_due_input(None, FIXED_TODAY) is None

    @pytest.mark.parametrize("bad", ["다음주", "2026/09/10", "+3주", "2026-02-31"])
    def test_알_수_없는_형식은_거부한다(self, bad):
        with pytest.raises(ValidationError):
            resolve_due_input(bad, FIXED_TODAY)


class TestDisplayWidth:
    def test_영문은_한_칸(self):
        assert display_width("abc") == 3

    def test_한글은_두_칸(self):
        assert display_width("장보기") == 6

    def test_섞이면_합산한다(self):
        assert display_width("ab장") == 4

    def test_빈_문자열은_0(self):
        assert display_width("") == 0


class TestFormatTable:
    def test_빈_목록은_안내_문구다(self):
        assert "없습니다" in format_table([])

    def test_제목이_들어간다(self, service):
        todo = service.add("장보기", due="2026-09-10", tags="집안일")
        table = format_table([todo])
        assert "장보기" in table
        assert "2026-09-10" in table
        assert "집안일" in table
        assert str(todo.id) in table

    def test_완료_표시가_구분된다(self, service):
        # 제목이 서로 부분 문자열이 되면 안 된다 ('미완료 항목' ⊃ '완료 항목')
        active = service.add("아직 남은 일")
        done = service.complete(service.add("끝낸 일").id)
        table = format_table([active, done])
        active_line = next(l for l in table.splitlines() if "아직 남은 일" in l)
        done_line = next(l for l in table.splitlines() if "끝낸 일" in l)
        assert "[ ]" in active_line
        assert "[x]" in done_line

    def test_한글_제목이_섞여도_열_폭이_일정하다(self, service):
        service.add("ab")
        service.add("한글제목입니다")
        service.add("mixed 섞인 title")
        lines = [l for l in format_table(service.list()).splitlines() if l.strip()]
        widths = {display_width(line) for line in lines}
        assert len(widths) == 1, f"줄마다 폭이 다르다: {widths}"

    def test_마감일이_없으면_하이픈으로_표시한다(self, service):
        table = format_table([service.add("마감없음")])
        assert "-" in table


class TestAddCommand:
    def test_추가하면_0을_돌려준다(self, run, service):
        assert run("add", "장보기") == 0
        assert [t.title for t in service.list()] == ["장보기"]

    def test_모든_옵션을_받는다(self, run, service):
        assert (
            run(
                "add", "장보기",
                "--due", "2026-09-10",
                "--tag", "집안일,장보기",
                "--priority", "high",
                "--notes", "우유",
            )
            == 0
        )
        todo = service.list()[0]
        assert todo.due_date == "2026-09-10"
        assert todo.notes == "우유"
        assert {t.name for t in todo.tags} == {"집안일", "장보기"}

    def test_오늘이라는_말을_날짜로_바꾼다(self, run, service):
        run("add", "발표", "--due", "오늘")
        assert service.list()[0].due_date == FIXED_TODAY

    def test_주입된_시계를_쓴다(self, run, service):
        # 실제 date.today()가 아니라 서비스의 고정 시계를 써야 한다.
        run("add", "발표", "--due", "+1d")
        assert service.list()[0].due_date == "2026-09-05"

    def test_지난_날짜는_등호_형태로_넘긴다(self, run, service):
        # '-2d'는 argparse가 옵션으로 오인하므로 --due=-2d 로 붙여 써야 한다.
        # resolve_due_input을 직접 부르는 유닛 테스트는 이 경로를 못 잡는다.
        assert run("add", "지난 과제", "--due=-2d") == 0
        assert service.list()[0].due_date == "2026-09-02"

    def test_붙여_쓰지_않은_지난_날짜는_사용법_오류다(self, run, service):
        with pytest.raises(SystemExit):
            run("add", "지난 과제", "--due", "-2d")

    def test_빈_제목은_1을_돌려주고_stderr에_안내한다(self, run, capsys):
        assert run("add", "   ") == 1
        assert capsys.readouterr().err.strip() != ""

    def test_잘못된_날짜는_1을_돌려준다(self, run):
        assert run("add", "장보기", "--due", "2026-02-31") == 1


class TestListCommand:
    def test_목록을_출력한다(self, run, service, capsys):
        service.add("장보기")
        assert run("list") == 0
        assert "장보기" in capsys.readouterr().out

    def test_범위_지름길_플래그(self, run, service, capsys):
        service.add("지난 것", due="2026-09-01")
        service.add("미래 것", due="2026-09-30")
        run("list", "--overdue")
        out = capsys.readouterr().out
        assert "지난 것" in out and "미래 것" not in out

    def test_scope_옵션으로도_지정한다(self, run, service, capsys):
        service.add("마감없는 것")
        service.add("마감있는 것", due="2026-09-30")
        run("list", "--scope", "no-due")
        out = capsys.readouterr().out
        assert "마감없는 것" in out and "마감있는 것" not in out

    def test_태그로_거른다(self, run, service, capsys):
        service.add("공부하기", tags="공부")
        service.add("청소하기", tags="집안일")
        run("list", "--tag", "공부")
        out = capsys.readouterr().out
        assert "공부하기" in out and "청소하기" not in out

    def test_키워드로_찾는다(self, run, service, capsys):
        service.add("장보기")
        service.add("청소하기")
        run("list", "--search", "장보")
        out = capsys.readouterr().out
        assert "장보기" in out and "청소하기" not in out

    def test_요약이_함께_출력된다(self, run, service, capsys):
        service.add("할 일", due="2026-09-01")
        run("list")
        assert "미완료" in capsys.readouterr().out


class TestStateCommands:
    def test_완료로_표시한다(self, run, service):
        todo = service.add("장보기")
        assert run("done", str(todo.id)) == 0
        assert service.get(todo.id).is_done is True

    def test_완료를_되돌린다(self, run, service):
        todo = service.complete(service.add("장보기").id)
        assert run("undone", str(todo.id)) == 0
        assert service.get(todo.id).is_done is False

    def test_없는_id는_1을_돌려준다(self, run, capsys):
        assert run("done", "9999") == 1
        assert "찾을 수 없" in capsys.readouterr().err


class TestRemoveCommand:
    def test_확인하면_지운다(self, run, service):
        todo = service.add("장보기")
        assert run("rm", str(todo.id), confirm=lambda _: True) == 0
        assert service.list() == []

    def test_거절하면_남는다(self, run, service, capsys):
        todo = service.add("장보기")
        assert run("rm", str(todo.id), confirm=lambda _: False) == 0
        assert len(service.list()) == 1
        assert "취소" in capsys.readouterr().out

    def test_yes_플래그는_묻지_않는다(self, run, service):
        todo = service.add("장보기")

        def 절대_불리면_안됨(_):
            raise AssertionError("--yes를 줬는데 확인을 물었다")

        assert run("rm", str(todo.id), "--yes", confirm=절대_불리면_안됨) == 0
        assert service.list() == []

    def test_없는_id는_1이고_확인도_묻지_않는다(self, run, capsys):
        def 절대_불리면_안됨(_):
            raise AssertionError("없는 id인데 확인을 물었다")

        assert run("rm", "9999", confirm=절대_불리면_안됨) == 1


class TestShowAndTags:
    def test_상세를_출력한다(self, run, service, capsys):
        todo = service.add("장보기", notes="우유 사기", due="2026-09-10", tags="집안일")
        assert run("show", str(todo.id)) == 0
        out = capsys.readouterr().out
        assert "우유 사기" in out and "집안일" in out and "2026-09-10" in out

    def test_완료된_항목의_상세에_완료시각이_나온다(self, run, service, capsys):
        todo = service.complete(service.add("장보기").id)
        run("show", str(todo.id))
        assert "완료" in capsys.readouterr().out

    def test_태그_목록을_출력한다(self, run, service, capsys):
        service.add("과제", tags="공부,집안일")
        assert run("tags") == 0
        out = capsys.readouterr().out
        assert "공부" in out and "집안일" in out

    def test_태그가_없으면_안내한다(self, run, capsys):
        assert run("tags") == 0
        assert "없습니다" in capsys.readouterr().out

    def test_태그_목록도_한글_폭을_보정한다(self, run, service, capsys):
        service.add("과제", tags="study,집안일,공부")
        run("tags")
        lines = [l for l in capsys.readouterr().out.splitlines() if l.strip()]
        assert len({display_width(l) for l in lines}) == 1


class TestEditCommand:
    def test_제목을_바꾼다(self, run, service):
        todo = service.add("장보기")
        assert run("edit", str(todo.id), "--title", "장보기(수정)") == 0
        assert service.get(todo.id).title == "장보기(수정)"

    def test_마감일을_비운다(self, run, service):
        todo = service.add("장보기", due="2026-09-10")
        assert run("edit", str(todo.id), "--due", "없음") == 0
        assert service.get(todo.id).due_date is None

    def test_태그를_교체한다(self, run, service):
        todo = service.add("과제", tags="공부")
        assert run("edit", str(todo.id), "--tag", "집안일") == 0
        assert [t.name for t in service.get(todo.id).tags] == ["집안일"]

    def test_안_준_필드는_그대로다(self, run, service):
        todo = service.add("과제", notes="메모", tags="공부")
        run("edit", str(todo.id), "--title", "새 제목")
        edited = service.get(todo.id)
        assert edited.notes == "메모"
        assert [t.name for t in edited.tags] == ["공부"]

    def test_없는_id는_1이다(self, run):
        assert run("edit", "9999", "--title", "없음") == 1


class TestParser:
    def test_서브커맨드_없이_부르면_사용법을_알린다(self, run, capsys):
        assert run() == 2
        assert "usage" in capsys.readouterr().out.lower()

    def test_알_수_없는_서브커맨드는_SystemExit이다(self, service):
        with pytest.raises(SystemExit):
            main(["없는명령"], service=service)
