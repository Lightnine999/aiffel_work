"""failure_cases.py와 같은 질문을 던지되, 도구 호출 앞에 하네스 검증(harness.py)을 끼워 넣은 버전.

모델이 도구를 부르면 하네스가 먼저 인자를 검증한다. 검증에 실패하면 실제 조회는 일어나지 않고,
실패 종류와 뒤 행동(action)만 모델에게 돌려준다.
실행: uv run --with langchain --with langchain-ollama python failure_cases_harness.py
"""

import asyncio
import json
from typing import Any

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

from harness import ToolError, call_with_policy


@tool
def get_inventory(sku: str, warehouse_id: str) -> dict[str, Any]:
    """승인된 창고에서 특정 상품의 현재 가용 재고를 읽기 전용으로 조회합니다.
    sku에는 상품 SKU를, warehouse_id에는 SEOUL-01 또는 BUSAN-02만 넣습니다.
    수량을 변경하지 않습니다. INVALID_SKU이면 SKU를 확인해 달라고 물어야 합니다."""
    if warehouse_id not in ("SEOUL-01", "BUSAN-02"):
        return {"error": "WAREHOUSE_NOT_ALLOWED"}
    return {"sku": sku, "warehouse_id": warehouse_id,
            "available_quantity": 7, "checked_at": "2026-08-27T01:55:00+09:00"}


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
]


def guarded_invoke(args: dict, user_text: str) -> dict:
    """하네스를 거쳐 도구를 실행한다. 검증 실패는 실패 종류와 뒤 행동을 담은 결과로 바꾼다.

    차단/통과 여부와 실제 조회 횟수를 출력해서 트레이스에 남긴다.
    """
    reached = []  # 하네스 검증을 통과해 실제 도구까지 도달한 호출

    def fetch(normalized: dict) -> dict:
        reached.append(normalized)
        return get_inventory.invoke(normalized)

    try:
        result = call_with_policy(fetch, args, user_text)
        print(f"    [하네스] 통과 · 실제 조회 {len(reached)}회 · 인자 {reached[0]}")
        return result
    except ToolError as exc:
        print(f"    [하네스] 차단 · kind={exc.kind} · action={exc.action} · 실제 조회 {len(reached)}회")
        return {"error": exc.kind, "action": exc.action, "message": exc.message}
    except Exception as exc:  # 도구 인자 자체가 맞지 않는 경우(예: warehouse_id 누락)
        print(f"    [하네스] 차단 · kind=tool_schema · 예외={type(exc).__name__} · 실제 조회 {len(reached)}회")
        return {"error": "tool_schema", "action": "ask_identifier", "message": f"{type(exc).__name__}"}


async def run_case(llm_with_tools, prompt: str, max_turns: int = 3):
    """모델이 도구를 부르면 하네스를 거쳐 실행하고 결과를 돌려주는 루프."""
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
            result = guarded_invoke(tc["args"], prompt)
            messages.append(ToolMessage(
                content=json.dumps(result, ensure_ascii=False),
                tool_call_id=tc["id"]))
    return calls, ai.content


async def main():
    llm = ChatOllama(model="qwen3.5:2b", temperature=0, reasoning=False)
    llm_with_tools = llm.bind_tools([get_inventory])

    for name, prompt, expected in CASES:
        print(f"=== {name}")
        print(f"질문: {prompt}")
        print(f"기대: {expected}")
        calls, answer = await run_case(llm_with_tools, prompt)
        print(f"도구 호출 {len(calls)}회: {calls}")
        print(f"최종 답: {answer}")
        print()


asyncio.run(main())
