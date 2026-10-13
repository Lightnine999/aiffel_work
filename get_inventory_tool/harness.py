"""get_inventory 하네스: 입력 검증, 실패 처리, 응답 필터링을 코드로 강제한다.

모델이 어떻게 판단하든 이 계층을 통과해야만 실제 조회가 일어난다.
"""

import json
import pathlib
import re
from dataclasses import dataclass

# 도구 정의(get_inventory.json)를 단일 출처로 읽는다. 값을 코드에 따로 적지 않는다.
DEFINITION = json.loads(
    (pathlib.Path(__file__).resolve().parent / "get_inventory.json").read_text(encoding="utf-8")
)
_PROPERTIES = DEFINITION["input_schema"]["properties"]
ALLOWED_WAREHOUSES = tuple(_PROPERTIES["warehouse_id"]["enum"])
SKU_MIN = _PROPERTIES["sku"]["minLength"]
SKU_MAX = _PROPERTIES["sku"]["maxLength"]
RESPONSE_FIELDS = tuple(DEFINITION["output"]["fields"])


@dataclass
class ToolError(Exception):
    kind: str      # 실패 종류
    action: str    # 실패 뒤 행동: ask_warehouse / ask_identifier / retry / stop
    message: str


def sku_appears_in(sku: str, user_text: str) -> bool:
    """SKU가 사용자 질문에 독립된 토큰으로 나타나는지 확인한다. 대소문자는 구분하지 않는다."""
    pattern = rf"(?<![A-Za-z0-9-]){re.escape(sku)}(?![A-Za-z0-9-])"
    return re.search(pattern, user_text, flags=re.IGNORECASE) is not None


def validate_input(args: dict, user_text: str) -> dict:
    """인자 스키마 검증. 통과하면 정규화된 인자를 돌려준다."""
    sku = args.get("sku")
    if not isinstance(sku, str) or not (SKU_MIN <= len(sku) <= SKU_MAX):
        # 빈 SKU나 추측한 SKU를 만들지 않고, 상품 식별자를 사용자에게 되묻는다
        raise ToolError("invalid_sku", "ask_identifier", "SKU는 필수이며 상품 식별자를 물어야 합니다")

    if not sku_appears_in(sku, user_text):
        # 모델이 지어낸 SKU는 형식이 맞아도 조회하지 않는다
        raise ToolError("sku_not_in_request", "ask_identifier", "질문에 없는 SKU입니다. 상품 식별자를 물어야 합니다")

    warehouse_id = args.get("warehouse_id")
    if warehouse_id is not None and warehouse_id not in ALLOWED_WAREHOUSES:
        # 허용되지 않은 창고 코드는 재호출하지 않고 허용 코드를 되묻는다
        raise ToolError("unknown_warehouse", "ask_warehouse", "허용되지 않은 창고입니다. 허용 코드를 물어야 합니다")

    return {"sku": sku, "warehouse_id": warehouse_id}


def filter_response(raw: dict) -> dict:
    """반환 형식 고정: 가용 수량과 확인 시각 관련 필드만 남긴다. 원가 등은 제거."""
    return {key: raw[key] for key in RESPONSE_FIELDS if key in raw}


def call_with_policy(fetch, args: dict, user_text: str, max_retries: int = 1) -> dict:
    """검증 → 조회 → 필터. 일시 오류만 1회 재시도하고, 검증 실패는 재시도하지 않는다."""
    normalized = validate_input(args, user_text)  # 검증 실패는 여기서 바로 ToolError로 빠진다
    attempts = 0
    while True:
        try:
            return filter_response(fetch(normalized))
        except TimeoutError as exc:  # 일시 오류만 재시도 대상
            attempts += 1
            if attempts > max_retries:
                raise ToolError("transient", "stop", str(exc)) from exc
