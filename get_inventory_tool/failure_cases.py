"""get_inventory 실패 사례를 실제 모델에 던져서 행동을 확인한다.

inventory_tool.py와 같은 도구 정의·모델 설정을 쓰고, 실패 사례 질문 3개만 돌린다.
실행: uv run --with langchain --with langchain-ollama python failure_cases.py
"""

import asyncio
import json
from typing import Any

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama


@tool
def get_inventory(sku: str, warehouse_id: str) -> dict[str, Any]:
    """승인된 창고에서 특정 상품의 현재 가용 재고를 읽기 전용으로 조회합니다.
    sku에는 상품 SKU를, warehouse_id에는 SEOUL-01 또는 BUSAN-02만 넣습니다.
    수량을 변경하지 않습니다. INVALID_SKU이면 SKU를 확인해 달라고 물어야 합니다."""
    if warehouse_id not in ("SEOUL-01", "BUSAN-02"):
        return {"error": "WAREHOUSE_NOT_ALLOWED"}
    return {"sku": sku, "warehouse_id": warehouse_id,
            "available_quantity": 7, "checked_at": "2026-08-27T01:55:00+09:00"}


# (사례 이름, 사용자 질문, 기대 행동)
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


async def run_case(llm_with_tools, prompt: str, max_turns: int = 3):
    """모델이 도구를 부르면 실행하고 결과를 돌려주는 루프. 호출 기록과 최종 답을 돌려준다."""
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
            try:
                result = get_inventory.invoke(tc["args"])
            except Exception as exc:  # 인자 검증 실패도 모델에게 그대로 알려 준다
                result = {"error": f"{type(exc).__name__}: {exc}"}
            messages.append(ToolMessage(
                content=json.dumps(result, ensure_ascii=False),
                tool_call_id=tc["id"]))
    return calls, ai.content


async def main():
    llm = ChatOllama(model="qwen3.5:2b", temperature=0, reasoning=False)
    llm_with_tools = llm.bind_tools([get_inventory])

    for name, prompt, expected in CASES:
        calls, answer = await run_case(llm_with_tools, prompt)
        print(f"=== {name}")
        print(f"질문: {prompt}")
        print(f"기대: {expected}")
        print(f"도구 호출 {len(calls)}회: {calls}")
        print(f"최종 답: {answer}")
        print()


asyncio.run(main())
