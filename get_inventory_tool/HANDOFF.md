# 인계 메모: get_inventory 도구 실습 (2026-10-12 기준)

## 한 줄 요약
`get_inventory`(승인된 창고의 SKU 가용 재고 조회, 읽기 전용) 도구를 두고, 로컬 모델(qwen3.5:2b, 온도 0)이 실패 사례 3건에서 어떻게 행동하는지 확인했다. 하네스(검증 계층)로 잘못된 호출을 막고, 결과를 트레이스로 기록했다.

## 폴더 구성 (모두 `get_inventory_tool/` 안)
| 파일 | 역할 |
|------|------|
| `get_inventory.json` | 도구 정의 (이름, 설명, 입력 스키마, 출력 필드, 실패 뒤 행동). 하네스가 읽는 단일 출처 |
| `harness.py` | 입력 검증, 질문 대조 규칙, 응답 필터, 재시도 정책. JSON에서 창고 코드·SKU 길이·응답 필드를 읽음 |
| `test_regression.py` | 회귀 테스트 11개 (실패 사례 3건 + 대조군). 전부 통과 |
| `mutation_check.py` | 하네스를 일부러 망가뜨린 변형 M1~M6로 테스트가 빨개지는지 확인. 전부 기대대로 빨개짐 |
| `inventory_tool.py` | 정상 질문 1건 실행 (질문: `BUSAN-02 창고의 SKU A-17 재고를 알려 줘`) |
| `failure_cases.py` | 실패 사례 3건을 하네스 없이 실행 |
| `failure_cases_harness.py` | 실패 사례 3건을 하네스 연결 + 차단/통과 로그와 함께 실행 |
| `tool-lab/` | 트레이스 `trace-01.txt` ~ `trace-10.txt`, 요약 `SUMMARY.md` |

## 실행 방법
Ollama가 켜져 있어야 한다.
```bash
cd ~/aiffel_work/get_inventory_tool
uv run --with langchain --with langchain-ollama python failure_cases_harness.py
```
테스트: `python3 -m unittest test_regression -v`
변형 실험: `python3 mutation_check.py`

트레이스는 덮어쓰지 않도록 `noclobber`를 켜고 저장한다.
```bash
set -o noclobber && uv run --with langchain --with langchain-ollama python failure_cases_harness.py > tool-lab/trace-11.txt 2>&1
```

## 지금까지 확인된 것
1. **정상 질문**: 4회 반복 모두 같은 호출 (`sku=A-17, warehouse_id=BUSAN-02`), 같은 답.
2. **실패 사례 2 (SKU 없음)**: 모델이 `SKU123456789`를 지어내 호출하려 한다. 하네스의 질문 대조 규칙이 이를 조회 전에 차단한다 (`sku_not_in_request`, 실제 조회 0회). 모델의 판단 자체는 바뀌지 않았다.
3. **실패 사례 1 (허용되지 않은 창고, `INCHEON-09`)**: 하네스가 차단하고 (`unknown_warehouse`, 실제 조회 0회), 허용 코드 SEOUL-01·BUSAN-02를 되묻는다.
4. **실패 사례 3 (원가 요청)**: 원가를 지어내지 않는다. 정상 조회 1회가 통과한다.
5. **하네스 버그 발견 및 수정**: 응답 필터가 `available_quantity`를 지워서, 하네스를 붙인 뒤 트레이스(06~10)의 사례 3 답에서 재고 수량이 빠졌다. JSON 연결 과정에서 필드 이름을 맞춰 고쳤다.

## 주의할 점
- **트레이스 06~10은 필터 버그가 있던 상태**의 기록이다. 사례 3 답에 수량이 빠진 것이 버그 때문이었음을 알고 봐야 한다. 수정 후 결과는 `trace-11`부터 나온다.
- 모든 트레이스는 질문당 1회 실행이다. 확률적 차이는 측정하지 않았다.
- 도구 구현은 가짜다. 어떤 SKU를 넣어도 수량 7을 돌려준다.
- `tool-lab/SUMMARY.md`에는 아직 필터 버그와 수정 내용이 없다. 다음 세션에서 반영이 필요하다.

## 남은 작업 (우선순위 순)
1. **`trace-11` 기록**: 필터 수정 후 `failure_cases_harness.py`를 실행해 사례 3에 수량이 다시 나오는지 확인.
2. **`SUMMARY.md` 갱신**: 필터 버그 발견·수정 내용과 06~10의 한계 추가.
3. **실패 뒤 행동을 JSON에서 읽기**: 지금은 `ask_identifier`, `ask_warehouse` 등이 코드에 하드코딩되어 있다. `get_inventory.json`의 `failure_handling`을 읽도록 바꾸면 정의가 한 곳에 모인다.
4. **모델 행동 개선 실험**: 모델이 여전히 `SKU123456789`를 요청한다. 프롬프트나 도구 설명(`description`)을 바꿔서 요청 자체가 줄어드는지 확인.
5. **반복 측정**: 같은 질문을 여러 번 돌려 확률적 차이 확인 (필요 시).

## 다음 세션 시작 시 할 일
- 이 파일을 읽고 `trace-11`부터 이어간다.
- 먼저 Ollama가 켜져 있는지 확인한다.
