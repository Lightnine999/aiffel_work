"""MCP 서버 — CLI와 같은 서비스 계층을 JSON-RPC로 노출한다.

MCP는 특별한 무엇이 아니라 stdio에 줄 단위 JSON-RPC 2.0을 주고받는 규약이다.
그래서 SDK 없이도 만들 수 있고, 여기서는 요청 dict를 넣어 응답 dict를 본다.

CLI와의 차이는 '무엇을 하는가'가 아니라 '누가 부르는가'다.
  CLI  사람이 셸에 타이핑 → 사람이 표를 읽는다
  MCP  모델이 도구를 호출 → 모델이 JSON을 읽는다
"""
from __future__ import annotations

import json

import pytest

from todoapp.mcp_server import TOOLS, handle
from todoapp.service import TodoService

FIXED_TODAY = "2026-09-04"


@pytest.fixture
def service(conn) -> TodoService:
    return TodoService(conn, today=lambda: FIXED_TODAY)


def req(method: str, params: dict | None = None, id_: int | None = 1) -> dict:
    body: dict = {"jsonrpc": "2.0", "method": method}
    if id_ is not None:
        body["id"] = id_
    if params is not None:
        body["params"] = params
    return body


def call(service, tool: str, args: dict | None = None) -> dict:
    return handle(
        req("tools/call", {"name": tool, "arguments": args or {}}), service
    )


def text_of(response: dict) -> str:
    return response["result"]["content"][0]["text"]


class TestHandshake:
    def test_initialize에_서버_정보를_돌려준다(self, service):
        res = handle(req("initialize", {"protocolVersion": "2024-11-05"}), service)
        assert res["result"]["serverInfo"]["name"] == "todoapp"
        assert "tools" in res["result"]["capabilities"]

    def test_클라이언트가_요청한_프로토콜_버전을_맞춰준다(self, service):
        res = handle(req("initialize", {"protocolVersion": "2024-11-05"}), service)
        assert res["result"]["protocolVersion"] == "2024-11-05"

    def test_알림에는_응답하지_않는다(self, service):
        # JSON-RPC 알림(id 없음)에 응답하면 클라이언트가 프로토콜 위반으로 본다
        assert handle(req("notifications/initialized", id_=None), service) is None

    def test_모르는_메서드는_32601(self, service):
        res = handle(req("todo/무엇인가"), service)
        assert res["error"]["code"] == -32601


class TestToolsList:
    def test_네_개를_노출한다(self, service):
        names = {t["name"] for t in TOOLS}
        assert names == {"list_todos", "today_summary", "add_todo", "complete_todo"}

    def test_모든_도구가_스키마를_갖는다(self, service):
        for tool in TOOLS:
            assert tool["description"]
            assert tool["inputSchema"]["type"] == "object"

    def test_tools_list가_같은_목록을_준다(self, service):
        res = handle(req("tools/list"), service)
        assert len(res["result"]["tools"]) == 4


class TestToolCalls:
    def test_today_summary는_건수를_돌려준다(self, service, conn):
        todo = service.add("설거지", due=FIXED_TODAY)
        service.complete(todo.id)
        # 트리거가 넣은 '지금'을 고정 시계에 맞춘다 (test_cli_summary와 같은 방식)
        conn.execute(
            "UPDATE todos SET completed_at = ? WHERE id = ?",
            (f"{FIXED_TODAY} 09:10:00", todo.id),
        )
        conn.commit()
        payload = json.loads(text_of(call(service, "today_summary")))
        assert payload["completed_today"] == 1
        assert payload["items"][0]["title"] == "설거지"

    def test_list_todos는_범위를_받는다(self, service):
        service.add("과제", due=FIXED_TODAY)
        service.add("책 읽기")
        payload = json.loads(text_of(call(service, "list_todos", {"scope": "today"})))
        assert [i["title"] for i in payload["items"]] == ["과제"]

    def test_list_todos는_우선순위도_받는다(self, service):
        service.add("과제", priority="high")
        service.add("설거지")
        payload = json.loads(
            text_of(call(service, "list_todos", {"priority": "high"}))
        )
        assert [i["title"] for i in payload["items"]] == ["과제"]

    def test_add_todo가_실제로_추가한다(self, service):
        call(service, "add_todo", {"title": "장보기", "due": "오늘"})
        assert [t.title for t in service.list()] == ["장보기"]

    def test_complete_todo가_완료로_바꾼다(self, service):
        todo = service.add("설거지")
        call(service, "complete_todo", {"id": todo.id})
        assert service.get(todo.id).is_done is True

    def test_없는_도구는_isError로_돌려준다(self, service):
        res = call(service, "todo/없는도구")
        # 도구 오류는 JSON-RPC 오류가 아니라 결과 안의 isError로 알린다.
        # 그래야 모델이 그 내용을 읽고 스스로 고쳐 다시 부를 수 있다.
        assert res["result"]["isError"] is True

    def test_잘못된_입력은_isError로_돌려준다(self, service):
        res = call(service, "add_todo", {"title": "과제", "priority": "아주높음"})
        assert res["result"]["isError"] is True
        assert "우선순위" in text_of(res)

    def test_없는_번호를_완료하면_isError(self, service):
        res = call(service, "complete_todo", {"id": 999})
        assert res["result"]["isError"] is True
