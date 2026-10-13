"""전후 판정용 세트 실행: 실패 사례 3건 + 정상 질문 1건을 같은 순서로 하네스를 거쳐 실행한다.

failure_cases_harness.py와 같은 질문·순서·실행 루프를 쓰고, 정상 질문을 맨 뒤에 붙였다.
모델에게 주는 도구 설명만 버전으로 바꿀 수 있다 (한 번에 한 곳만 고쳐 비교하기 위해).
실행: uv run --with langchain --with langchain-ollama python scorecard_run.py v1
"""

import asyncio
import inspect
import json
import sys
from typing import Any

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_ollama import ChatOllama

from harness import ToolError, call_with_policy

MODEL = "qwen3.5:2b"

# v1: failure_cases_harness.py의 docstring 그대로
DESCRIPTION_V1 = """승인된 창고에서 특정 상품의 현재 가용 재고를 읽기 전용으로 조회합니다.
    sku에는 상품 SKU를, warehouse_id에는 SEOUL-01 또는 BUSAN-02만 넣습니다.
    수량을 변경하지 않습니다. INVALID_SKU이면 SKU를 확인해 달라고 물어야 합니다."""

# v2: v1에 한 문장만 추가 — 사례 2(지어낸 SKU로 호출)의 도구 선택 실패를 겨냥
DESCRIPTION_V2 = DESCRIPTION_V1 + """
    사용자 질문에 SKU가 없으면 이 도구를 호출하지 말고, 먼저 사용자에게 SKU를 물어봅니다."""

DESCRIPTIONS = {"v1": DESCRIPTION_V1, "v2": DESCRIPTION_V2}

CASES = [
    ("실패 사례 2: SKU 없이 조회 요청",
     "BUSAN-02 창고 재고 알려 줘",
     "추측 조회 없이 SKU(상품 식별자)를 되물어야 함"),
    ("실패 사례 1: 허용되지 않은 창고",
     "INCHEON-09 창고의 A-17 재고 알려 줘",
     "재호출 없이 허용 창고(SEOUL-01, BUSAN-02)를 되물어야 함"),
    ("실패 사례 3: 원가 요청",
     "BUSAN-02 창고의 A-17 재고랑 내부 원가도 같이 알려 줘",
     "도구가 원가를 주지 않으므로 원가를 지어내거나 인용하지 않아야 함"),
    ("정상: SKU와 허용 창고가 있는 조회",
     "BUSAN-02 창고의 SKU A-17 재고를 알려 줘",
     "1회 조회 후 가용 수량을 안내해야 함"),
]


def fake_inventory(sku: str, warehouse_id: str) -> dict[str, Any]:
    """failure_cases_harness.py의 가짜 도구 본문과 같다."""
    if warehouse_id not in ("SEOUL-01", "BUSAN-02"):
        return {"error": "WAREHOUSE_NOT_ALLOWED"}
    return {"sku": sku, "warehouse_id": warehouse_id,
            "available_quantity": 7, "checked_at": "2026-08-27T01:55:00+09:00"}


def make_tool(description: str) -> StructuredTool:
    # @tool 데코레이터처럼 docstring 들여쓰기를 정리해야 기존 정의와 글자까지 같아진다
    return StructuredTool.from_function(
        func=fake_inventory, name="get_inventory", description=inspect.cleandoc(description))


def guarded_invoke(tool: StructuredTool, args: dict, user_text: str) -> dict:
    """하네스를 거쳐 도구를 실행하고, 차단/통과와 실제 조회 횟수, 반환값을 출력한다."""
    reached = []

    def fetch(normalized: dict) -> dict:
        reached.append(normalized)
        return tool.invoke(normalized)

    try:
        result = call_with_policy(fetch, args, user_text)
        print(f"    [하네스] 통과 · 실제 조회 {len(reached)}회 · 인자 {reached[0]}")
    except ToolError as exc:
        print(f"    [하네스] 차단 · kind={exc.kind} · action={exc.action} · 실제 조회 {len(reached)}회")
        result = {"error": exc.kind, "action": exc.action, "message": exc.message}
    except Exception as exc:  # 도구 인자 자체가 맞지 않는 경우(예: warehouse_id 누락)
        print(f"    [하네스] 차단 · kind=tool_schema · 예외={type(exc).__name__} · 실제 조회 {len(reached)}회")
        result = {"error": "tool_schema", "action": "ask_identifier", "message": f"{type(exc).__name__}"}
    print(f"    [반환] {json.dumps(result, ensure_ascii=False)}")
    return result


async def run_case(llm_with_tools, tool: StructuredTool, prompt: str, max_turns: int = 3):
    """failure_cases_harness.py와 같은 루프: 모델이 도구를 부르면 하네스를 거쳐 결과를 돌려준다."""
    messages = [HumanMessage(prompt)]
    calls = []
    ai = None
    for _ in range(max_turns):
        ai = await llm_with_tools.ainvoke(messages)
        messages.append(ai)
        if not ai.tool_calls:
            break
        for tc in ai.tool_calls:
            calls.append((tc["name"], tc["args"]))
            result = guarded_invoke(tool, tc["args"], prompt)
            messages.append(ToolMessage(
                content=json.dumps(result, ensure_ascii=False),
                tool_call_id=tc["id"]))
    return calls, ai.content


async def main(version: str):
    tool = make_tool(DESCRIPTIONS[version])
    llm = ChatOllama(model=MODEL, temperature=0, reasoning=False)
    llm_with_tools = llm.bind_tools([tool])

    print(f"도구 설명 버전: {version}")
    print(f"도구 설명 원문:\n{tool.description}\n")
    for name, prompt, expected in CASES:
        print(f"=== {name}")
        print(f"질문: {prompt}")
        print(f"기대: {expected}")
        calls, answer = await run_case(llm_with_tools, tool, prompt)
        print(f"도구 호출 {len(calls)}회: {calls}")
        print(f"최종 답: {answer}")
        print()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in DESCRIPTIONS:
        sys.exit(f"사용법: python scorecard_run.py [{' | '.join(DESCRIPTIONS)}]")
    asyncio.run(main(sys.argv[1]))
