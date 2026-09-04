"""터미널 인터페이스. 서비스 계층만 호출하고 SQL은 모른다."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from datetime import date, timedelta
from typing import Callable, Sequence

from todoapp.config import get_db_path
from todoapp.database import open_db
from todoapp.models import (
    PRIORITY_LABELS,
    Todo,
    ValidationError,
    normalize_due_date,
)
from todoapp.service import SCOPES, TodoNotFound, TodoService

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
    sub.add_parser("tags", help="태그 목록")
    return parser


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
    print(format_table(service.list(args.scope, tag=args.tag, keyword=args.search)))
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


_COMMANDS: dict[str, Callable[[argparse.Namespace, TodoService, Confirm], int]] = {
    "add": _cmd_add,
    "list": _cmd_list,
    "done": _cmd_done,
    "undone": _cmd_undone,
    "show": _cmd_show,
    "rm": _cmd_rm,
    "edit": _cmd_edit,
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

    if service is not None:
        return _dispatch(args, service, confirm or _default_confirm)
    with open_db(get_db_path()) as conn:
        return _dispatch(args, TodoService(conn), confirm or _default_confirm)


if __name__ == "__main__":
    raise SystemExit(main())
