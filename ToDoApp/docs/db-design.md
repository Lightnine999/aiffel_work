# ToDoApp DB 설계

로컬 SQLite 단일 파일(`db/todo.db`). 서버·계정·비용 없음.

## 표 3개

| 표 | 역할 | 행 예시 |
|---|---|---|
| `todos` | 할 일 본체 | "AIFFEL 과제 제출", 마감 2026-09-04, 미완료 |
| `tags` | 태그 사전 | "공부", "집안일" |
| `todo_tags` | 할 일 ↔ 태그 연결 | (1번 할 일, 공부) |

관계: `todos` 1 : N `todo_tags` N : 1 `tags` → 실질적으로 **할 일 ↔ 태그는 N:M**.
할 일 하나에 태그 여러 개, 태그 하나에 할 일 여러 개.

## 왜 태그를 별도 표로 뺐나

`todos.tags = "공부,집안일"` 처럼 한 칸에 몰아넣는 방식과 비교하면:

| | 콤마 문자열 | 별도 표 (채택) |
|---|---|---|
| 태그로 필터 | `LIKE '%공부%'` → 전체 훑기, "공부방"도 걸림 | 인덱스 타는 정확한 JOIN |
| 오타 관리 | "공부"/"공부 " 따로 쌓임 | `UNIQUE`로 원천 차단 |
| 이름 변경 | 모든 행 문자열 수정 | `tags` 한 줄만 수정 |
| 태그 색상 추가 | 넣을 자리 없음 | `tags.color` 열 하나 |

## 열 설계 근거

**`todos`**
- `is_done INTEGER 0/1` — SQLite에 BOOLEAN 타입이 없다. `CHECK (is_done IN (0,1))`로 값을 묶는다.
- `due_date TEXT 'YYYY-MM-DD'` — SQLite에 DATE 타입도 없다. 이 형식은 **문자 정렬 = 날짜 정렬**이라 `ORDER BY due_date`가 그냥 맞는다. `CHECK`로 실존하는 날짜만 통과시킨다(`2026-02-31` 거부).
- `priority 1/2/3` — 마감일이 같을 때 순서를 가르는 2차 기준.
- `completed_at` — 완료 시각. "이번 주에 몇 개 끝냈나" 같은 회고용. 트리거가 자동 기록.
- `updated_at` — 트리거가 자동 갱신. 앱 코드가 매번 챙길 필요 없다.

**`tags`**
- `name UNIQUE COLLATE NOCASE` — "공부"와 "공부"의 대소문자 변형을 같은 태그로 취급.

**`todo_tags`**
- 복합 PK `(todo_id, tag_id)` — 같은 태그를 같은 할 일에 두 번 붙이는 사고를 구조로 막는다. 별도 `id` 열이 필요 없다.
- 양쪽 `ON DELETE CASCADE` — 할 일을 지우면 연결도 함께 사라진다. 고아 행 청소 코드 불필요.

## 인덱스 3개

- `idx_todos_due_date` — 마감일 정렬·"오늘 할 일"
- `idx_todos_is_done` — 미완료만 보기
- `idx_todo_tags_tag` — 태그로 역방향 검색

작은 표에 인덱스를 더 붙이면 쓰기만 느려진다. 이 3개에서 시작한다.

## 뷰 2개 (앱 코드에서 SQL 반복 안 하려고)

- `v_today_todos` — 마감일이 오늘이거나 지난 미완료 항목
- `v_todo_list` — 목록 화면용. 태그를 `GROUP_CONCAT`으로 한 줄로 합쳐 N+1 쿼리를 피한다

## 함정 (CRITICAL)

**SQLite는 외래키 검사가 기본 꺼져 있다.** 연결할 때마다 켜야 `CASCADE`와 참조 무결성이 동작한다.

```python
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")   # 연결마다 필수
```

이걸 빼먹으면 스키마는 멀쩡한데 고아 행이 조용히 쌓인다.

## 검증 결과 (2026-09-04)

`sqlite3`로 실제 실행해 확인:

- 표 3개 / 인덱스 3개 / 트리거 2개 / 뷰 2개 생성 성공
- CRUD 4종, 태그 JOIN 검색, `v_today_todos`·`v_todo_list` 조회 정상
- 완료 표시 → `completed_at` 자동 기록, 되돌리면 자동 `NULL`
- 할 일 삭제 → `todo_tags` 연결행 CASCADE 삭제 확인
- 제약 위반 4종 모두 거부: `2026/09/04`(형식), `2026-02-31`(없는 날), 공백 제목, 태그명 중복

## 실행

```bash
sqlite3 db/todo.db < db/schema.sql
```
