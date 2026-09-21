"""터미널 인터페이스. 서비스 계층만 호출하고 SQL은 모른다."""

from __future__ import annotations

import argparse
import getpass
import re
import sys
import unicodedata
from datetime import date, timedelta
from typing import Callable, Sequence

from todoapp import auth_flow
from todoapp.auth_flow import NotLoggedIn
from todoapp.config import get_storage_backend
from todoapp.models import (
    PRIORITY_LABELS,
    Todo,
    ValidationError,
    normalize_due_date,
)
from todoapp.service import SCOPES, TodoNotFound, TodoService
from todoapp.session import SESSION_PATH, clear as clear_session
from todoapp.session import load as load_session
from todoapp.session import save as save_session
from todoapp.stores import build_store
from todoapp.supabase_client import AuthError

_RELATIVE_DAYS_RE = re.compile(r"^([+-])(\d+)d$", re.IGNORECASE)
_TODAY_WORDS = {"today", "오늘"}
_TOMORROW_WORDS = {"tomorrow", "내일"}
_CLEAR_WORDS = {"", "none", "없음", "null"}


# ---------------------------------------------------------------- 입력 해석


def resolve_due_input(raw: str | None, today: str) -> str | None:
    """사람이 쓰는 표현을 'YYYY-MM-DD'로 바꾼다.

    받는 형태: ISO 날짜 / today·오늘 / tomorrow·내일 / +7d·-1d / none·없음(비우기)
    """
    if raw is None:
        return None
    value = str(raw).strip()
    lowered = value.lower()
    if lowered in _CLEAR_WORDS:
        return None
    base = date.fromisoformat(today)
    if lowered in _TODAY_WORDS:
        return base.isoformat()
    if lowered in _TOMORROW_WORDS:
        return (base + timedelta(days=1)).isoformat()
    match = _RELATIVE_DAYS_RE.match(value)
    if match:
        sign = 1 if match.group(1) == "+" else -1
        return (base + timedelta(days=sign * int(match.group(2)))).isoformat()
    return normalize_due_date(value)  # ISO가 아니면 여기서 ValidationError


# ---------------------------------------------------------------- 출력 서식


def display_width(text: str) -> int:
    """터미널에서 차지하는 칸 수. 한글·한자·일본어는 두 칸이다."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    """표시 폭 기준으로 오른쪽을 채운다. str.ljust는 글자 수로 세서 못 쓴다."""
    return text + " " * max(0, width - display_width(text))


_HEADERS = ("ID", "상태", "제목", "마감일", "우선", "태그")


def _to_row(todo: Todo) -> tuple[str, ...]:
    return (
        str(todo.id),
        "[x]" if todo.is_done else "[ ]",
        todo.title,
        todo.due_date or "-",
        PRIORITY_LABELS[todo.priority],
        ", ".join(t.name for t in todo.tags) or "-",
    )


def format_table(todos: Sequence[Todo]) -> str:
    """할 일 목록을 고정 폭 표로. 모든 줄의 표시 폭이 같도록 맞춘다."""
    if not todos:
        return "할 일이 없습니다."
    rows = [_HEADERS, *(_to_row(t) for t in todos)]
    widths = [max(display_width(row[i]) for row in rows) for i in range(len(_HEADERS))]
    gap = "  "
    total = sum(widths) + len(gap) * (len(widths) - 1)
    lines = [
        gap.join(_pad(cell, widths[i]) for i, cell in enumerate(row)) for row in rows
    ]
    # 모든 줄이 정확히 total 폭이다 (마지막 칸까지 채우므로 rstrip하지 않는다)
    return "\n".join([lines[0], "-" * total, *lines[1:]])


def format_detail(todo: Todo) -> str:
    lines = [
        f"[{todo.id}] {todo.title}",
        f"  상태     : {'완료' if todo.is_done else '미완료'}",
        f"  마감일   : {todo.due_date or '-'}",
        f"  우선순위 : {PRIORITY_LABELS[todo.priority]}",
        f"  태그     : {', '.join(t.name for t in todo.tags) or '-'}",
        f"  메모     : {todo.notes or '-'}",
        f"  생성     : {todo.created_at}",
        f"  수정     : {todo.updated_at}",
    ]
    if todo.completed_at:
        lines.append(f"  완료시각 : {todo.completed_at}")
    return "\n".join(lines)


def format_summary(counts: dict[str, int]) -> str:
    return (
        f"전체 {counts['total']} · 미완료 {counts['active']} · "
        f"오늘까지 {counts['today']} · 기한 지남 {counts['overdue']}"
    )


# ---------------------------------------------------------------- 파서

_DUE_HELP = "마감일 (2026-09-10 / 오늘 / 내일 / +7d / 지난날은 --due=-2d)"


def _register_add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("add", help="할 일 추가")
    p.add_argument("title", help="할 일 제목")
    # 지난 날짜(-2d)는 argparse가 옵션으로 오인하므로 --due=-2d 형태로 붙여 써야 한다.
    p.add_argument("--due", help=_DUE_HELP)
    p.add_argument("--tag", help="태그, 쉼표로 구분 (예: 공부,집안일)")
    p.add_argument("--priority", help="우선순위 (high/normal/low 또는 1/2/3)")
    p.add_argument("--notes", help="메모")


def _register_list(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("list", help="목록 보기")
    p.add_argument("--scope", choices=SCOPES, default="all", help="범위")
    shortcuts = p.add_mutually_exclusive_group()
    for flag, scope, help_text in (
        ("--all", "all", "전체 (기본)"),
        ("--active", "active", "미완료만"),
        ("--done", "done", "완료만"),
        ("--today", "today", "오늘까지 마감인 미완료"),
        ("--overdue", "overdue", "기한이 지난 미완료"),
    ):
        shortcuts.add_argument(
            flag, dest="scope", action="store_const", const=scope, help=help_text
        )
    p.add_argument("--tag", help="이 태그가 붙은 것만")
    p.add_argument("--search", help="제목·메모에서 찾기")
    p.add_argument(
        "--priority", help="이 우선순위만 (high/normal/low 또는 1/2/3)"
    )


def _register_id_only(sub: argparse._SubParsersAction) -> None:
    for name, help_text in (
        ("done", "완료로 표시"),
        ("undone", "완료 되돌리기"),
        ("show", "상세 보기"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("id", type=int, help="할 일 번호")


def _register_rm(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("rm", help="삭제")
    p.add_argument("id", type=int, help="할 일 번호")
    p.add_argument("-y", "--yes", action="store_true", help="확인 없이 삭제")


def _register_edit(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("edit", help="내용 수정")
    p.add_argument("id", type=int, help="할 일 번호")
    p.add_argument("--title")
    p.add_argument("--due", help=f"{_DUE_HELP}. '없음'을 주면 비운다")
    p.add_argument("--tag", help="태그 전체를 이것으로 교체 (빈 문자열이면 전부 제거)")
    p.add_argument("--priority")
    p.add_argument("--notes")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="todo", description="로컬 SQLite에 저장하는 할 일 관리 도구"
    )
    sub = parser.add_subparsers(dest="command")
    _register_add(sub)
    _register_list(sub)
    _register_id_only(sub)
    _register_rm(sub)
    _register_edit(sub)
    sub.add_parser("summary", help="오늘 완료한 일 요약")
    sub.add_parser("tags", help="태그 목록")
    _register_auth(sub)
    return parser


def _register_auth(sub: argparse._SubParsersAction) -> None:
    """Supabase 저장소를 쓸 때 필요한 로그인 명령."""
    for name, help_text in (("login", "로그인"), ("signup", "회원가입")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--email", help="이메일 (생략하면 물어봅니다)")
        p.add_argument(
            "--password",
            help="비밀번호 (생략하면 화면에 안 보이게 물어봅니다. 생략을 권합니다)",
        )
    sub.add_parser("logout", help="로그아웃")
    sub.add_parser("whoami", help="현재 로그인한 계정 보기")
    p_reset = sub.add_parser("reset-password", help="비밀번호 찾기 (메일로 코드 받기)")
    p_reset.add_argument("--email", help="이메일 (생략하면 물어봅니다)")


# ---------------------------------------------------------------- 명령 처리

Confirm = Callable[[str], bool]


def _cmd_add(args: argparse.Namespace, service: TodoService, confirm: Confirm) -> int:
    todo = service.add(
        args.title,
        notes=args.notes,
        due=resolve_due_input(args.due, service.today()),
        priority=args.priority,
        tags=args.tag,
    )
    print(f"추가했습니다. [{todo.id}] {todo.title}")
    return 0


def _cmd_list(args: argparse.Namespace, service: TodoService, confirm: Confirm) -> int:
    print(
        format_table(
            service.list(
                args.scope,
                tag=args.tag,
                keyword=args.search,
                priority=args.priority,
            )
        )
    )
    print(f"\n{format_summary(service.summary())}")
    return 0


def _cmd_done(args: argparse.Namespace, service: TodoService, confirm: Confirm) -> int:
    print(f"완료로 표시했습니다. [{args.id}] {service.complete(args.id).title}")
    return 0


def _cmd_undone(args: argparse.Namespace, service: TodoService, confirm: Confirm) -> int:
    print(f"미완료로 되돌렸습니다. [{args.id}] {service.reopen(args.id).title}")
    return 0


def _cmd_show(args: argparse.Namespace, service: TodoService, confirm: Confirm) -> int:
    print(format_detail(service.get(args.id)))
    return 0


def _cmd_rm(args: argparse.Namespace, service: TodoService, confirm: Confirm) -> int:
    todo = service.get(args.id)  # 없으면 확인을 묻기 전에 예외
    if not args.yes and not confirm(f"[{todo.id}] {todo.title} 을(를) 삭제할까요?"):
        print("취소했습니다.")
        return 0
    service.delete(args.id)
    print(f"삭제했습니다. [{todo.id}] {todo.title}")
    return 0


def _cmd_edit(args: argparse.Namespace, service: TodoService, confirm: Confirm) -> int:
    # 옵션을 주지 않으면 None이다. 그 필드는 service에 넘기지 않아 UNSET으로 남는다.
    fields: dict[str, object] = {}
    if args.title is not None:
        fields["title"] = args.title
    if args.notes is not None:
        fields["notes"] = args.notes or None
    if args.due is not None:
        fields["due"] = resolve_due_input(args.due, service.today())
    if args.priority is not None:
        fields["priority"] = args.priority
    if args.tag is not None:
        fields["tags"] = args.tag
    todo = service.edit(args.id, **fields)  # type: ignore[arg-type]
    print(f"수정했습니다. [{todo.id}] {todo.title}")
    return 0


def _cmd_summary(args: argparse.Namespace, service: TodoService, confirm: Confirm) -> int:
    """오늘 완료한 일을 표로 보여주고 건수를 센다."""
    day = service.today()
    done_today = service.completed_on(day)
    print(f"오늘({day}) 완료한 일")
    print(format_table(done_today) if done_today else "완료한 일이 없습니다.")
    print(f"\n오늘 완료 {len(done_today)}건 · {format_summary(service.summary())}")
    return 0


def _cmd_tags(args: argparse.Namespace, service: TodoService, confirm: Confirm) -> int:
    tags = service.all_tags()
    if not tags:
        print("등록된 태그가 없습니다.")
        return 0
    # 한글 태그명은 두 칸을 차지하므로 표시 폭으로 맞춘다
    width = max(display_width(t.name) for t in tags)
    for tag in tags:
        print(f"  {_pad(tag.name, width)}  ({tag.color})")
    return 0


def _ask_credentials(args: argparse.Namespace) -> tuple[str, str]:
    """이메일·비밀번호를 확보한다. 비밀번호는 getpass로 받아 화면에 남기지 않는다."""
    email = args.email or input("이메일: ").strip()
    password = args.password or getpass.getpass("비밀번호: ")
    return email, password


def _cmd_login(args: argparse.Namespace) -> int:
    email, password = _ask_credentials(args)
    tokens = auth_flow.login(email, password)
    save_session(tokens, SESSION_PATH)
    print(f"로그인했습니다. ({tokens.email})")
    return 0


def _cmd_signup(args: argparse.Namespace) -> int:
    email, password = _ask_credentials(args)
    tokens = auth_flow.signup(email, password)
    save_session(tokens, SESSION_PATH)
    print(f"가입하고 로그인했습니다. ({tokens.email})")
    return 0


def _cmd_logout(args: argparse.Namespace) -> int:
    if load_session(SESSION_PATH) is None:
        print("로그인 상태가 아닙니다.")
        return 0
    auth_flow.revoke()
    clear_session(SESSION_PATH)
    print("로그아웃했습니다.")
    return 0


def _ask_new_password() -> str:
    """새 비밀번호를 두 번 받아 대조한다. 화면에는 남지 않는다."""
    first = getpass.getpass("새 비밀번호 (6자 이상): ")
    second = getpass.getpass("새 비밀번호 확인: ")
    if first != second:
        raise AuthError("두 비밀번호가 일치하지 않습니다.")
    return first


def _cmd_reset_password(args: argparse.Namespace) -> int:
    """이메일 → 메일 링크 붙여넣기 → 새 비밀번호를 한 명령 안에서 처리한다."""
    email = args.email or input("이메일: ").strip()
    auth_flow.request_password_reset(email)
    # 계정이 없어도 같은 문구다 — 다르게 답하면 가입 여부가 새어 나간다
    print(f"재설정 링크를 메일로 보냈습니다. ({email})")
    print("메일함(스팸함 포함)에서 'Reset your password' 메일을 여세요.")
    print()
    print("  ⚠️  링크를 '누르지' 마시고, 우클릭 → 링크 주소 복사 로 가져오세요.")
    print("     링크는 한 번만 쓸 수 있어서, 누르면 터미널에서 못 씁니다.")
    print("     (브라우저에서 그냥 눌러 진행하셔도 됩니다 — 그 경우 이 명령은 취소하세요.)")
    print()

    link = input("복사한 링크 주소: ")
    password = _ask_new_password()
    tokens = auth_flow.confirm_password_reset(link, password)
    save_session(tokens, SESSION_PATH)
    print(f"비밀번호를 바꿨습니다. 로그인 상태입니다. ({tokens.email})")
    return 0


def _cmd_whoami(args: argparse.Namespace) -> int:
    tokens = load_session(SESSION_PATH)
    if tokens is None:
        print("로그인 상태가 아닙니다. `todo login` 으로 로그인하세요.")
        return 0
    # 토큰 값은 출력하지 않는다
    print(f"{tokens.email or '(이메일 미확인)'} · 저장소 {get_storage_backend()}")
    return 0


_AUTH_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "login": _cmd_login,
    "signup": _cmd_signup,
    "logout": _cmd_logout,
    "whoami": _cmd_whoami,
    "reset-password": _cmd_reset_password,
}


_COMMANDS: dict[str, Callable[[argparse.Namespace, TodoService, Confirm], int]] = {
    "add": _cmd_add,
    "list": _cmd_list,
    "done": _cmd_done,
    "undone": _cmd_undone,
    "show": _cmd_show,
    "rm": _cmd_rm,
    "edit": _cmd_edit,
    "summary": _cmd_summary,
    "tags": _cmd_tags,
}


# ---------------------------------------------------------------- 진입점


def _default_confirm(question: str) -> bool:
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def _dispatch(args: argparse.Namespace, service: TodoService, confirm: Confirm) -> int:
    """명령을 실행하고 종료 코드를 돌려준다. 사용자 오류는 stderr + 1."""
    try:
        return _COMMANDS[args.command](args, service, confirm)
    except ValidationError as exc:
        print(f"입력 오류: {exc}", file=sys.stderr)
        return 1
    except TodoNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 1


def main(
    argv: Sequence[str] | None = None,
    *,
    service: TodoService | None = None,
    confirm: Confirm | None = None,
) -> int:
    """CLI 진입점. 종료 코드를 돌려준다 (0 성공 / 1 사용자 오류 / 2 사용법 오류)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2

    if args.command in _AUTH_COMMANDS:
        # 인증 명령은 저장소가 필요 없다
        try:
            return _AUTH_COMMANDS[args.command](args)
        except (AuthError, NotLoggedIn) as exc:
            print(str(exc), file=sys.stderr)
            return 1

    if service is not None:
        return _dispatch(args, service, confirm or _default_confirm)

    try:
        store = _open_store()
    except (NotLoggedIn, AuthError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        return _dispatch(args, TodoService(store), confirm or _default_confirm)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def _open_store():
    """설정에 맞는 저장소를 연다.

    Supabase면 저장된 세션을 물린다. 토큰이 갱신되면 파일도 갱신한다 —
    안 하면 매 실행마다 갱신 왕복이 한 번씩 더 든다.
    """
    if get_storage_backend() == "sqlite":
        return build_store("sqlite")
    tokens = load_session(SESSION_PATH)
    if tokens is None:
        raise NotLoggedIn(
            "Supabase 저장소를 쓰려면 로그인이 필요합니다: python3 todo.py login"
        )
    store = build_store("supabase", tokens=tokens)
    fresh = getattr(store, "tokens", None)
    if fresh is not None and fresh != tokens:
        save_session(fresh, SESSION_PATH)
    return store


if __name__ == "__main__":
    raise SystemExit(main())
