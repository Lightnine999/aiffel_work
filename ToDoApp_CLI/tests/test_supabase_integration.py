"""실제 Supabase 프로젝트 대상 통합 테스트.

`.env`에 SUPABASE_URL/ANON_KEY가 없으면 통째로 건너뛴다. 다른 사람이
이 저장소를 받아도 나머지 테스트는 그대로 돌아야 하기 때문이다.

여기서 증명하는 것 두 가지 — 이게 이 작업 전체의 핵심 증거다:
  1. 계정 B는 계정 A의 행을 읽지도 고치지도 지우지도 못한다 (RLS)
  2. 로그인하지 않은 anon 키로는 아무 행도 못 읽는다 (GRANT + RLS)

테스트 계정은 대표님 프로젝트 안의 일회용 계정이다. 실제 데이터가 없다.
"""
from __future__ import annotations

import os
import uuid

import pytest
from dotenv import load_dotenv

from todoapp.models import local_date_of
from todoapp.service import TodoService
from todoapp.stores.supabase_store import SupabaseStore
from todoapp.supabase_client import AuthError, build_client, sign_in, sign_up

load_dotenv()

pytestmark = pytest.mark.skipif(
    not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY")),
    reason="SUPABASE_URL / SUPABASE_ANON_KEY 가 없어 통합 테스트를 건너뜁니다",
)

PASSWORD = os.getenv("SUPABASE_TEST_PASSWORD", "todoapp-test-pw-2026")
EMAIL_A = os.getenv("SUPABASE_TEST_EMAIL_A", "todoapp-test-a@example.com")
EMAIL_B = os.getenv("SUPABASE_TEST_EMAIL_B", "todoapp-test-b@example.com")

# 실행마다 고유한 꼬리표. 남은 데이터가 다음 실행을 오염시키지 않게 한다.
RUN = uuid.uuid4().hex[:8]


def _account(email: str):
    """계정을 확보한다. 이미 있으면 로그인한다 (여러 번 돌려도 안전)."""
    client = build_client()
    try:
        tokens = sign_up(client, email, PASSWORD)
    except AuthError:
        tokens = sign_in(client, email, PASSWORD)
    from todoapp.supabase_client import attach_session

    attach_session(client, tokens)
    store = SupabaseStore(client, user_id=tokens.user_id)
    return store, tokens


@pytest.fixture(scope="module")
def account_a():
    store, tokens = _account(EMAIL_A)
    yield store, tokens
    _cleanup(store)


@pytest.fixture(scope="module")
def account_b():
    store, tokens = _account(EMAIL_B)
    yield store, tokens
    _cleanup(store)


def _cleanup(store: SupabaseStore) -> None:
    """이번 실행이 만든 행만 지운다."""
    for todo in store.todos.list():
        if RUN in (todo.title or ""):
            store.todos.delete(todo.id)


@pytest.fixture
def service_a(account_a):
    return TodoService(account_a[0])


@pytest.fixture
def service_b(account_b):
    return TodoService(account_b[0])


# ---------------------------------------------------------------- 기본 왕복


class TestRoundTrip:
    def test_추가하고_읽는다(self, service_a):
        todo = service_a.add(
            f"통합 확인 {RUN}",
            notes="메모입니다",
            due="2026-09-10",
            priority="high",
            tags="공부,집안일",
        )
        assert todo.id is not None
        again = service_a.get(todo.id)
        assert again.title == f"통합 확인 {RUN}"
        assert again.notes == "메모입니다"
        assert again.due_date == "2026-09-10"
        assert again.priority == 1
        assert [t.name for t in again.tags] == ["공부", "집안일"]

    def test_완료_표시가_트리거로_시각을_남긴다(self, service_a):
        todo = service_a.add(f"완료 확인 {RUN}")
        done = service_a.complete(todo.id)
        assert done.is_done is True
        assert done.completed_at is not None
        reopened = service_a.reopen(todo.id)
        assert reopened.is_done is False
        assert reopened.completed_at is None

    def test_Postgres가_준_완료시각을_오늘로_읽는다(self, service_a):
        """`summary` 명령이 클라우드에서도 도는지 확인한다.

        Postgres는 timestamptz를 ISO+오프셋(UTC)으로 준다. 가짜 클라이언트
        테스트로는 이 실제 문자열 모양을 확인할 수 없다 (HANDOFF 함정 ④).
        읽지 못하면 local_date_of가 None을 주고 요약이 조용히 0건이 된다.
        """
        todo = service_a.add(f"오늘 요약 {RUN}")
        service_a.complete(todo.id)
        stored = service_a.get(todo.id)

        assert local_date_of(stored.completed_at) == service_a.today()
        assert todo.id in {t.id for t in service_a.completed_on()}

    def test_수정하고_태그를_교체한다(self, service_a):
        todo = service_a.add(f"수정 확인 {RUN}", tags="공부")
        edited = service_a.edit(todo.id, title=f"수정됨 {RUN}", tags="운동")
        assert edited.title == f"수정됨 {RUN}"
        assert [t.name for t in edited.tags] == ["운동"]

    def test_마감일_범위로_거른다(self, service_a):
        todo = service_a.add(f"지난 것 {RUN}", due="2026-01-01")
        overdue_ids = {t.id for t in service_a.list("overdue")}
        assert todo.id in overdue_ids

    def test_우선순위로_거른다(self, service_a):
        """`list --priority`가 실제 PostgREST에서 도는지 확인한다.

        가짜 클라이언트는 eq 호출이 기록됐는지만 본다. 서버가 그 필터를
        실제로 받아주는지는 여기서만 드러난다 (HANDOFF 함정 ④).
        """
        높음 = service_a.add(f"높음 확인 {RUN}", priority="high")
        낮음 = service_a.add(f"낮음 확인 {RUN}", priority="low")

        found = {t.id for t in service_a.list(priority="high")}
        assert 높음.id in found
        assert 낮음.id not in found

    def test_키워드로_찾는다(self, service_a):
        todo = service_a.add(f"장보기특이단어 {RUN}")
        found = service_a.list("all", keyword="장보기특이단어")
        assert todo.id in {t.id for t in found}

    def test_삭제하면_사라진다(self, service_a):
        todo = service_a.add(f"삭제 확인 {RUN}")
        service_a.delete(todo.id)
        from todoapp.service import TodoNotFound

        with pytest.raises(TodoNotFound):
            service_a.get(todo.id)

    def test_잘못된_입력은_서버에_가기_전에_막힌다(self, service_a):
        from todoapp.models import ValidationError

        with pytest.raises(ValidationError):
            service_a.add(f"날짜오류 {RUN}", due="2026-02-31")


# ---------------------------------------------------------------- RLS 격리


class TestRowLevelSecurity:
    """이 작업 전체의 핵심 증거. B가 A의 행에 닿지 못해야 한다."""

    @pytest.fixture
    def a_todo(self, service_a):
        return service_a.add(f"A의 비밀 할일 {RUN}", tags="A전용태그")

    def test_B는_A의_할_일을_목록에서_못_본다(self, a_todo, service_b):
        b_ids = {t.id for t in service_b.list("all")}
        assert a_todo.id not in b_ids

    def test_B는_A의_할_일을_id로도_못_읽는다(self, a_todo, account_b):
        rows = account_b[0].todos.get(a_todo.id)
        assert rows is None

    def test_B는_A의_할_일을_수정하지_못한다(self, a_todo, account_b, service_a):
        changed = account_b[0].todos.update(a_todo.id, title="B가 바꿈")
        assert changed is False
        # A쪽에서 보면 그대로여야 한다
        assert service_a.get(a_todo.id).title == f"A의 비밀 할일 {RUN}"

    def test_B는_A의_할_일을_완료로_바꾸지_못한다(self, a_todo, account_b, service_a):
        assert account_b[0].todos.set_done(a_todo.id, True) is False
        assert service_a.get(a_todo.id).is_done is False

    def test_B는_A의_할_일을_지우지_못한다(self, a_todo, account_b, service_a):
        assert account_b[0].todos.delete(a_todo.id) is False
        assert service_a.get(a_todo.id) is not None  # 여전히 살아 있다

    def test_B는_A의_태그를_못_본다(self, a_todo, service_b):
        b_tag_names = {t.name for t in service_b.all_tags()}
        assert "A전용태그" not in b_tag_names

    def test_B는_A의_할_일에_태그를_붙이지_못한다(self, a_todo, account_b, service_a):
        try:
            account_b[0].set_tags(a_todo.id, ["B가붙인태그"])
        except Exception:
            pass  # 정책 위반으로 거부되는 것도 정상
        names = {t.name for t in service_a.get(a_todo.id).tags}
        assert "B가붙인태그" not in names

    def test_같은_이름_태그를_각자_가질_수_있다(self, service_a, service_b):
        """태그 유일성이 (user_id, name)이라 서로 충돌하지 않는다."""
        shared = f"공용이름{RUN}"
        a = service_a.add(f"A 태그테스트 {RUN}", tags=shared)
        b = service_b.add(f"B 태그테스트 {RUN}", tags=shared)
        assert [t.name for t in a.tags] == [shared]
        assert [t.name for t in b.tags] == [shared]
        assert a.tags[0].id != b.tags[0].id  # 서로 다른 행이다

    def test_A는_자기_할_일을_정상적으로_다룬다(self, a_todo, service_a):
        """대조군 — 정책이 남을 막을 뿐 본인은 막지 않는다."""
        assert service_a.get(a_todo.id).id == a_todo.id
        assert service_a.complete(a_todo.id).is_done is True
        service_a.reopen(a_todo.id)


# ---------------------------------------------------------------- anon 차단


class TestAnonymousAccess:
    """로그인하지 않은 anon 키로는 아무것도 못 해야 한다."""

    @pytest.fixture
    def anon(self):
        return build_client()  # 세션을 붙이지 않는다

    @pytest.mark.parametrize("table", ["todos", "tags", "todo_tags"])
    def test_읽지_못한다(self, anon, table, service_a):
        service_a.add(f"anon 차단 확인 {RUN}")  # 읽힐 데이터가 있는 상태로 만든다
        with pytest.raises(Exception) as exc:
            anon.table(table).select("*").limit(1).execute()
        assert "42501" in str(exc.value) or "permission" in str(exc.value).lower()

    def test_쓰지_못한다(self, anon):
        with pytest.raises(Exception):
            anon.table("todos").insert({"title": f"anon이 넣음 {RUN}"}).execute()

    @pytest.mark.parametrize(
        "fn,params",
        [
            ("create_todo_with_tags", {"p_title": "anon"}),
            ("upsert_tags", {"p_names": ["anon"]}),
            ("set_todo_tags", {"p_todo_id": 1, "p_tags": []}),
        ],
    )
    def test_RPC도_실행하지_못한다(self, anon, fn, params):
        with pytest.raises(Exception) as exc:
            anon.rpc(fn, params).execute()
        assert "42501" in str(exc.value) or "permission" in str(exc.value).lower()
