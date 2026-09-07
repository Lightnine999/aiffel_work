# Todo 앱

## 개요

할 일을 추가·완료·조회하는 1인용 앱. **Python 3** + SQLite/Supabase.

저장소는 `.env`의 `STORAGE` 한 줄로 갈아끼운다 (`sqlite` | `supabase`).
CLI와 웹 두 프론트가 `todoapp/service.py` 하나를 공유한다.
상세 인수인계는 `HANDOFF.md`를 읽는다.

## 명령

- 목록: `python3 todo.py list`
- 추가: `python3 todo.py add "<내용>"`
- 완료: `python3 todo.py done <번호>`
- 오늘 완료 요약: `python3 todo.py summary`

그 밖에: `undone` `show` `rm` `edit` `tags` `login` `signup` `logout` `whoami` `reset-password`
웹은 `python3 app.py` → http://localhost:5001

로그인 없이 둘러볼 때: `STORAGE=sqlite python3 todo.py list`

## 규칙

- 데이터는 `todo.db`에 저장한다. UI 문구는 **존댓말**로.
- **저장소가 둘이다. 새 기능은 양쪽에 구현한다** — `sqlite_store.py`와 `supabase_store.py`.
  두 저장소의 차이(태그 유일성·원자성·와일드카드·완료시각 시간대)는 `HANDOFF.md` §6에 있다.
- **계층 경계를 지킨다.** `cli.py`와 `web/`에는 SQL·`sqlite3`·`supabase`가 없다.
  SQL은 `db/*.sql`과 `repository.py`·`supabase_store.py`에만 둔다.
  `tests/test_supabase_store.py::TestLayerBoundary`가 검사한다.
- **테스트를 먼저 쓴다** (RED → GREEN). 완료 주장 전에 반드시 실행한다.
  ```bash
  python3 -m pytest tests/ -q                                              # 449개
  python3 -m pytest tests/ -q --ignore=tests/test_supabase_integration.py  # 425개 (네트워크 없이)
  ```
- 완료시각(`completed_at`)은 **DB 트리거가 채운다.** 앱에서 따로 쓰지 않는다.
- 날짜·시간 계산은 암산하지 않는다. `date` 명령이나 `python3 -c "from datetime ..."`을 쓴다.

## 하지 말 것

- ❌ **`todo.db`(실데이터)를 직접 지우거나 덮어쓰지 말 것.** 실험은 `DB_PATH`로 임시 파일을 지정한다.
  ```bash
  STORAGE=sqlite DB_PATH=/tmp/smoke.db python3 todo.py add "테스트"
  ```
- ❌ `service_role` / `sb_secret_` / JWT Secret 키를 `.env`에 넣기 (RLS가 무력화된다)
- ❌ Supabase RPC 함수를 `security definer`로 바꾸기 (RLS를 우회해버린다)
- ❌ `app.py`의 host를 `0.0.0.0`으로 바꾸기 (CSRF 토큰이 없다)
- ❌ 포트를 5000으로 되돌리기 (macOS AirPlay가 점유한다)
- ❌ 한쪽 저장소만 고치기
- ❌ `completed_at`을 `[:10]`으로 잘라 날짜 비교하기 (클라우드에서 하루 어긋난다)
