"""`todo.py summary` — 오늘 완료한 일 요약.

완료시각은 저장소마다 모양이 다르다 (§HANDOFF 6).
  SQLite   : '2026-09-07 16:33:12'      naive · **로컬시각**
  Postgres : '2026-09-07T07:33:12+00:00' ISO  · **UTC**
그래서 '오늘'을 판정하려면 앞 10글자를 자르는 것으로는 안 된다.
UTC 23시 30분은 서울에서 이미 다음 날 아침 8시 30분이다.
"""
from __future__ import annotations

import os
import time

import pytest

from todoapp.cli import main
from todoapp.models import local_date_of
from todoapp.service import TodoService

FIXED_TODAY = "2026-09-04"


@pytest.fixture
def tz_seoul():
    """로컬 시간대를 서울로 못 박는다. 어느 기계에서 돌려도 결과가 같아야 한다."""
    old = os.environ.get("TZ")
    os.environ["TZ"] = "Asia/Seoul"
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


@pytest.fixture
def service(conn) -> TodoService:
    return TodoService(conn, today=lambda: FIXED_TODAY)


@pytest.fixture
def run(service):
    def _run(*argv, confirm=None):
        return main(list(argv), service=service, confirm=confirm or (lambda _: True))

    return _run


def _set_completed_at(conn, todo_id: int, value: str | None) -> None:
    """트리거가 넣은 '지금'을 원하는 시각으로 옮긴다 (테스트 셋업 전용).

    트리거가 실시각을 넣으므로, 고정 시계를 쓰는 테스트에서는 여기서 맞춰줘야 한다.
    """
    conn.execute("UPDATE todos SET completed_at = ? WHERE id = ?", (value, todo_id))
    conn.commit()


class TestLocalDateOf:
    def test_로컬시각_문자열은_날짜만_잘라낸다(self, tz_seoul):
        assert local_date_of("2026-09-07 16:33:12") == "2026-09-07"

    def test_UTC_시각은_로컬_날짜로_바꾼다(self, tz_seoul):
        # 서울은 UTC+9 — UTC 9/6 23:30은 로컬로 9/7 08:30이다
        assert local_date_of("2026-09-06T23:30:00+00:00") == "2026-09-07"

    def test_Z_접미사도_읽는다(self, tz_seoul):
        assert local_date_of("2026-09-06T23:30:00Z") == "2026-09-07"

    def test_소수점_초가_붙어도_읽는다(self, tz_seoul):
        assert local_date_of("2026-09-06T23:30:00.123456+00:00") == "2026-09-07"

    def test_없으면_None(self):
        assert local_date_of(None) is None

    def test_읽을_수_없는_값은_None(self):
        # 요약 한 줄 때문에 명령 전체가 죽지 않아야 한다
        assert local_date_of("어제쯤") is None


class TestCompletedOn:
    def test_오늘_완료한_것만_돌려준다(self, service, conn):
        오늘 = service.add("설거지").id
        어제 = service.add("빨래").id
        service.complete(오늘)
        service.complete(어제)
        _set_completed_at(conn, 오늘, f"{FIXED_TODAY} 09:10:00")
        _set_completed_at(conn, 어제, "2026-09-03 22:00:00")

        assert [t.id for t in service.completed_on()] == [오늘]

    def test_날짜를_주면_그_날로_조회한다(self, service, conn):
        어제 = service.add("빨래").id
        service.complete(어제)
        _set_completed_at(conn, 어제, "2026-09-03 22:00:00")

        assert [t.id for t in service.completed_on("2026-09-03")] == [어제]

    def test_미완료는_제외한다(self, service):
        service.add("장보기")
        assert service.completed_on() == []

    def test_완료시각이_비어_있으면_제외한다(self, service, conn):
        todo_id = service.add("설거지").id
        service.complete(todo_id)
        _set_completed_at(conn, todo_id, None)

        assert service.completed_on() == []

    def test_UTC로_저장된_완료시각도_로컬_날짜로_센다(self, service, conn, tz_seoul):
        todo_id = service.add("설거지").id
        service.complete(todo_id)
        # Postgres가 주는 모양. UTC 9/3 23:30 = 서울 9/4 08:30 → 오늘로 세야 한다
        _set_completed_at(conn, todo_id, "2026-09-03T23:30:00+00:00")

        assert [t.id for t in service.completed_on()] == [todo_id]


class TestSummaryCommand:
    def test_오늘_완료한_목록과_건수를_출력한다(self, run, service, conn, capsys):
        설거지 = service.add("설거지").id
        발표 = service.add("발표 준비").id
        service.add("장보기")  # 미완료
        for todo_id in (설거지, 발표):
            service.complete(todo_id)
            _set_completed_at(conn, todo_id, f"{FIXED_TODAY} 09:10:00")

        assert run("summary") == 0
        out = capsys.readouterr().out
        assert "설거지" in out
        assert "발표 준비" in out
        assert "장보기" not in out
        assert "오늘 완료 2건" in out

    def test_완료한_것이_없으면_없다고_알린다(self, run, capsys):
        assert run("summary") == 0
        out = capsys.readouterr().out
        assert "오늘 완료 0건" in out

    def test_전체_집계도_함께_보여준다(self, run, service, capsys):
        service.add("장보기")
        assert run("summary") == 0
        assert "미완료 1" in capsys.readouterr().out
