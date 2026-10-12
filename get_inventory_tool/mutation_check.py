"""하네스 변형(mutant) 실험: 원본은 건드리지 않고 복사본에서만 깨뜨려 테스트가 빨개지는지 확인한다.

실행: python3 mutation_check.py
복사본은 실행 후 삭제된다.
"""

import pathlib
import shutil
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE / ".mutants"

MUTANTS = {
    "baseline (변형 없음)": [],
    "M1 SKU 검증 제거": [
        ("if not isinstance(sku, str) or not (SKU_MIN <= len(sku) <= SKU_MAX):", "if False:"),
    ],
    "M2 창고 enum 검증 제거": [
        ("if warehouse_id is not None and warehouse_id not in ALLOWED_WAREHOUSES:", "if False:"),
    ],
    "M3 응답 필터 제거 (원가 노출)": [
        ("return filter_response(fetch(normalized))", "return fetch(normalized)"),
    ],
    "M4 재시도 상한 제거": [
        ("if attempts > max_retries:", "if False:"),
    ],
    "M5 검증 우회 (검증 실패도 호출)": [
        (
            "normalized = validate_input(args, user_text)  # 검증 실패는 여기서 바로 ToolError로 빠진다",
            'normalized = {"sku": args.get("sku"), "warehouse_id": args.get("warehouse_id")}',
        ),
    ],
    "M6 질문 대조 규칙 제거 (지어낸 SKU 통과)": [
        ("if not sku_appears_in(sku, user_text):", "if False:"),
    ],
}


def main() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    try:
        for label, patches in MUTANTS.items():
            dest = WORK / label.split()[0]
            dest.mkdir(parents=True)
            for f in HERE.glob("*.py"):
                shutil.copy(f, dest / f.name)
            text = (dest / "harness.py").read_text(encoding="utf-8")
            for old, new in patches:
                assert text.count(old) == 1, f"패턴이 정확히 1번 있어야 함: {old}"
                text = text.replace(old, new)
            (dest / "harness.py").write_text(text, encoding="utf-8")

            result = subprocess.run(
                ["python3", "-m", "unittest", "test_regression"],
                cwd=dest, capture_output=True, text=True,
            )
            summary = result.stderr.strip().splitlines()[-1]
            failed = [
                line.split(" ", 1)[1].split(" (")[0]
                for line in result.stderr.splitlines()
                if line.startswith(("FAIL:", "ERROR:"))
            ]
            print(f"== {label}: {summary}")
            for name in failed:
                print(f"   - 실패: {name}")
    finally:
        shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    main()
