"""MCP 서버. 서비스 계층만 호출하고 SQL은 모른다 — cli.py와 같은 위치의 진입점이다.

MCP는 특별한 런타임이 아니라 **stdio에 줄 단위 JSON-RPC 2.0**을 주고받는 규약이다.
그래서 SDK 없이 표준 라이브러리만으로 구현했다 (의존성을 늘리지 않으려는 이유도 있다).

cli.py와의 차이는 '무엇을 하는가'가 아니라 '누가 부르는가'다:
  cli.py       사람이 셸에 타이핑한다 → 사람이 고정폭 표를 읽는다
  mcp_server   모델이 도구를 호출한다 → 모델이 JSON을 읽는다
그래서 출력 형식만 다르다. 유스케이스는 service.py 하나를 공유한다.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Iterable

from todoapp.models import Todo, ValidationError
from todoapp.service import SCOPES, TodoNotFound, TodoService

SERVER_NAME = "todoapp"
SERVER_VERSION = "0.1.0"

# 우리가 말할 수 있는 프로토콜 버전. 클라이언트가 아는 것이 있으면 그걸 쓴다.
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_todos",
        "description": (
            "할 일 목록을 조회한다. scope로 범위를, tag·keyword·priority로 좁힌다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": list(SCOPES),
                    "description": "기본 all. today는 오늘까지 마감인 미완료.",
                },
                "tag": {"type": "string"},
                "keyword": {"type": "string", "description": "제목·메모에서 찾기"},
                "priority": {
                    "type": "string",
                    "description": "high/normal/low 또는 1/2/3",
                },
            },
        },
    },
    {
        "name": "today_summary",
        "description": "오늘 완료한 할 일과 건수, 전체 집계를 돌려준다.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "add_todo",
        "description": "할 일을 추가한다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "due": {
                    "type": "string",
                    "description": "2026-09-10 / 오늘 / 내일 / +7d / 없음",
                },
                "priority": {"type": "string", "description": "high/normal/low"},
                "tags": {"type": "string", "description": "쉼표로 구분"},
                "notes": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "complete_todo",
        "description": "할 일을 완료로 표시한다. 완료시각은 DB가 기록한다.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
    },
]


# ---------------------------------------------------------------- 직렬화


def _todo_to_dict(todo: Todo) -> dict[str, Any]:
    """모델이 읽을 형태로. 고정폭 표가 아니라 구조를 준다."""
    return {
        "id": todo.id,
        "title": todo.title,
        "done": todo.is_done,
        "due_date": todo.due_date,
        "priority": todo.priority,
        "tags": [t.name for t in todo.tags],
        "notes": todo.notes,
        "completed_at": todo.completed_at,
    }


def _items(todos: Iterable[Todo]) -> list[dict[str, Any]]:
    return [_todo_to_dict(t) for t in todos]


# ---------------------------------------------------------------- 도구 구현


def _tool_list_todos(args: dict, service: TodoService) -> dict:
    todos = service.list(
        args.get("scope", "all"),
        tag=args.get("tag"),
        keyword=args.get("keyword"),
        priority=args.get("priority"),
    )
    return {"count": len(todos), "items": _items(todos)}


def _tool_today_summary(args: dict, service: TodoService) -> dict:
    day = service.today()
    done_today = service.completed_on(day)
    return {
        "date": day,
        "completed_today": len(done_today),
        "items": _items(done_today),
        "counts": service.summary(),
    }


def _tool_add_todo(args: dict, service: TodoService) -> dict:
    todo = service.add(
        args["title"],
        notes=args.get("notes"),
        due=_resolve_due(args.get("due"), service.today()),
        priority=args.get("priority"),
        tags=args.get("tags"),
    )
    return {"added": _todo_to_dict(todo)}


def _tool_complete_todo(args: dict, service: TodoService) -> dict:
    todo = service.complete(int(args["id"]))
    return {"completed": _todo_to_dict(todo)}


def _resolve_due(raw: str | None, today: str) -> str | None:
    """'오늘·내일·+7d'를 CLI와 똑같이 해석한다. 규칙이 갈라지면 안 된다."""
    from todoapp.cli import resolve_due_input

    return resolve_due_input(raw, today)


_TOOL_IMPLS: dict[str, Callable[[dict, TodoService], dict]] = {
    "list_todos": _tool_list_todos,
    "today_summary": _tool_today_summary,
    "add_todo": _tool_add_todo,
    "complete_todo": _tool_complete_todo,
}


# ---------------------------------------------------------------- JSON-RPC


def _ok(request_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _err(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _text_result(request_id: Any, payload: dict, is_error: bool = False) -> dict:
    """도구 결과는 content 배열에 담는다. 오류도 여기서 알린다.

    도구 실패를 JSON-RPC 오류로 올리지 않는 이유: 프로토콜 오류는 클라이언트가
    삼켜버려 모델이 못 본다. isError로 내려주면 모델이 이유를 읽고 스스로
    고쳐 다시 부를 수 있다.
    """
    return _ok(
        request_id,
        {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "isError": is_error,
        },
    )


def _negotiate(requested: str | None) -> str:
    if requested in SUPPORTED_PROTOCOLS:
        return requested
    return SUPPORTED_PROTOCOLS[0]


def handle(request: dict, service: TodoService) -> dict | None:
    """요청 하나를 처리한다. 알림(id 없음)이면 None을 준다."""
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}

    if request_id is None:  # 알림에는 응답하지 않는다
        return None

    if method == "initialize":
        return _ok(
            request_id,
            {
                "protocolVersion": _negotiate(params.get("protocolVersion")),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    if method == "tools/list":
        return _ok(request_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        impl = _TOOL_IMPLS.get(name)
        if impl is None:
            return _text_result(request_id, {"error": f"알 수 없는 도구: {name}"}, True)
        try:
            return _text_result(request_id, impl(args, service))
        except (ValidationError, TodoNotFound) as exc:
            return _text_result(request_id, {"error": str(exc)}, True)
        except (KeyError, TypeError, ValueError) as exc:
            return _text_result(request_id, {"error": f"잘못된 인자: {exc}"}, True)

    return _err(request_id, -32601, f"지원하지 않는 메서드: {method}")


# ---------------------------------------------------------------- 진입점


def serve(service: TodoService, stdin=None, stdout=None) -> int:
    """stdio 루프. 한 줄에 요청 하나, 한 줄에 응답 하나."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response = _err(None, -32700, "JSON을 읽을 수 없습니다")
        else:
            response = handle(request, service)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
    return 0


def main() -> int:
    from todoapp.cli import _open_store

    store = _open_store()
    try:
        return serve(TodoService(store))
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()
