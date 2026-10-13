"""get_inventory 실패 사례 회귀 테스트.

정의서 실패 사례 3건을 그대로 옮긴 테스트다.
실행: python3 -m unittest test_regression -v
"""

import unittest

from harness import ToolError, call_with_policy


class FakeInventory:
    """호출 횟수를 세는 가짜 재고 API. 실제 네트워크를 타지 않는다."""

    def __init__(self, response=None, raise_timeouts=0):
        self.calls = []
        self.response = response or {
            "sku": "ABC-1234",
            "warehouse_id": "SEOUL-01",
            "available_quantity": 42,
            "checked_at": "2026-10-12T09:00:00+09:00",
        }
        self.raise_timeouts = raise_timeouts

    def __call__(self, args):
        self.calls.append(args)
        if self.raise_timeouts > 0:
            self.raise_timeouts -= 1
            raise TimeoutError("upstream timeout")
        return dict(self.response)


class Case1_UnknownWarehouseNotRetried(unittest.TestCase):
    """실패 사례 1: 존재하지 않는 창고 코드를 임의로 넣어 같은 오류를 반복 호출했다."""

    def test_unknown_warehouse_asks_for_allowed_codes_without_calling_api(self):
        api = FakeInventory()
        with self.assertRaises(ToolError) as ctx:
            call_with_policy(api, {"sku": "ABC-1234", "warehouse_id": "INCHEON-09"},
                             "INCHEON-09 창고의 ABC-1234 재고 알려 줘")

        self.assertEqual(ctx.exception.kind, "unknown_warehouse")
        self.assertEqual(ctx.exception.action, "ask_warehouse")
        self.assertEqual(len(api.calls), 0, "검증 실패인데 API가 호출됨 (재호출 금지 위반)")


class Case2_MissingSkuNotGuessed(unittest.TestCase):
    """실패 사례 2: SKU를 모른 채 가장 비슷한 상품을 골라 조회했다."""

    def test_missing_sku_asks_for_identifier_without_calling_api(self):
        api = FakeInventory()
        with self.assertRaises(ToolError) as ctx:
            call_with_policy(api, {"warehouse_id": "SEOUL-01"}, "SEOUL-01 창고 재고 알려 줘")

        self.assertEqual(ctx.exception.kind, "invalid_sku")
        self.assertEqual(ctx.exception.action, "ask_identifier")
        self.assertEqual(len(api.calls), 0, "SKU 없이 API가 호출됨 (추측 조회 금지 위반)")

    def test_sku_too_short_is_rejected(self):
        api = FakeInventory()
        with self.assertRaises(ToolError):
            call_with_policy(api, {"sku": "AB"}, "AB 재고 알려 줘")
        self.assertEqual(len(api.calls), 0)

    def test_fabricated_sku_not_in_request_is_rejected(self):
        """실제 실패 재현: 모델이 'SKU123456789'를 지어냈다. 형식은 맞지만 질문에 없으므로 막아야 한다."""
        api = FakeInventory()
        with self.assertRaises(ToolError) as ctx:
            call_with_policy(api, {"sku": "SKU123456789", "warehouse_id": "BUSAN-02"},
                             "BUSAN-02 창고 재고 알려 줘")

        self.assertEqual(ctx.exception.kind, "sku_not_in_request")
        self.assertEqual(ctx.exception.action, "ask_identifier")
        self.assertEqual(len(api.calls), 0, "질문에 없는 SKU로 API가 호출됨")

    def test_partial_sku_match_is_rejected(self):
        """'ABC-12'는 질문의 'ABC-1234' 일부일 뿐이므로 독립 토큰이 아니다."""
        api = FakeInventory()
        with self.assertRaises(ToolError) as ctx:
            call_with_policy(api, {"sku": "ABC-12", "warehouse_id": "SEOUL-01"},
                             "SEOUL-01 창고의 ABC-1234 재고 알려 줘")
        self.assertEqual(ctx.exception.kind, "sku_not_in_request")
        self.assertEqual(len(api.calls), 0)

    def test_sku_match_is_case_insensitive(self):
        api = FakeInventory()
        call_with_policy(api, {"sku": "abc-1234", "warehouse_id": "SEOUL-01"},
                         "SEOUL-01 창고의 ABC-1234 재고 알려 줘")
        self.assertEqual(len(api.calls), 1)


class Case3_CostNotLeaked(unittest.TestCase):
    """실패 사례 3: 응답의 내부 원가를 최종 답에 인용했다."""

    def test_internal_cost_is_removed_from_response(self):
        api = FakeInventory(response={
            "sku": "ABC-1234",
            "warehouse_id": "SEOUL-01",
            "available_quantity": 42,
            "checked_at": "2026-10-12T09:00:00+09:00",
            "unit_cost": 8500,          # 내부 원가: 답변에 나오면 안 됨
            "supplier_margin": 0.31,
        })
        result = call_with_policy(api, {"sku": "ABC-1234", "warehouse_id": "SEOUL-01"},
                                  "SEOUL-01 창고의 ABC-1234 재고랑 원가 알려 줘")

        self.assertEqual(set(result), {"sku", "warehouse_id", "available_quantity", "checked_at"})
        self.assertNotIn("unit_cost", result)
        self.assertNotIn("supplier_margin", result)


class ControlCases(unittest.TestCase):
    """회귀 방지 대조군: 정상 경로는 막히지 않아야 하고, 일시 오류 재시도는 1회만 허용된다."""

    def test_valid_request_passes_through_once(self):
        api = FakeInventory()
        result = call_with_policy(api, {"sku": "ABC-1234", "warehouse_id": "BUSAN-02"},
                                  "BUSAN-02 창고의 ABC-1234 재고 알려 줘")
        self.assertEqual(result["available_quantity"], 42)
        self.assertEqual(len(api.calls), 1)

    def test_warehouse_optional_when_omitted(self):
        api = FakeInventory()
        call_with_policy(api, {"sku": "ABC-1234"}, "ABC-1234 재고 알려 줘")
        self.assertEqual(len(api.calls), 1)

    def test_transient_error_retried_exactly_once(self):
        api = FakeInventory(raise_timeouts=1)
        result = call_with_policy(api, {"sku": "ABC-1234"}, "ABC-1234 재고 알려 줘")
        self.assertEqual(result["available_quantity"], 42)
        self.assertEqual(len(api.calls), 2)

    def test_transient_error_stops_after_one_retry(self):
        api = FakeInventory(raise_timeouts=5)
        with self.assertRaises(ToolError) as ctx:
            call_with_policy(api, {"sku": "ABC-1234"}, "ABC-1234 재고 알려 줘")
        self.assertEqual(ctx.exception.action, "stop")
        self.assertEqual(len(api.calls), 2, "재시도는 최대 1회여야 함 (총 2회 호출)")


if __name__ == "__main__":
    unittest.main()
