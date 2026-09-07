# ToDoApp 작업 인수인계

> 다음 세션에서 이 문서만 읽고 바로 이어서 작업할 수 있게 정리한 문서다.
> 작성 2026-09-07 · `main` 기준 `7858199`
> 이 문서의 모든 명령과 수치는 작성 시점에 실제로 실행해 확인했다.

> ⚠️ **2026-09-07 이후 작업은 `../ToDoApp_CLI/`에서 한다. 이 폴더는 그 시점에 멈췄다.**
> 최신 내용은 `ToDoApp_CLI/HANDOFF.md`를 볼 것 (CLI `summary` 명령 추가 · 테스트 449개).

---

## 1. 한 문단 요약

"내 컴퓨터에서 도는 Todo 앱" PRD 한 장으로 시작해, 로컬 SQLite로 만들고
Supabase(클라우드 Postgres)로 이행했다. 저장소를 `.env` 한 줄로 갈아끼울 수 있고,
클라우드 쪽은 RLS로 "내 행만" 보이게 DB가 강제한다. CLI와 웹 두 프론트가 같은 코어를 쓴다.

| 항목 | 값 |
|---|---|
| 상태 | **완료** · `main` 병합됨 (PR #1, #2) |
| 커밋 | 19개 |
| 코드 | 2,660줄 (`todoapp/`) |
| 테스트 | **434개 통과** (실연결 통합 23개 포함) |
| 브랜치 | `main` 하나 (작업 브랜치 삭제 완료) |

---

## 2. 지금 바로 실행하기

```bash
cd /Users/kwonkwanggoo/aiffel_work/ToDoApp

# 테스트 — 아무 설정 없이 바로 된다
python3 -m pytest tests/ -q                                              # 전체 434개
python3 -m pytest tests/ -q --ignore=tests/test_supabase_integration.py  # 네트워크 없이 411개

# 설정·접속 확인 (키 값은 출력되지 않음)
python3 scripts/check_env.py --connect

# 웹
python3 app.py                      # → http://localhost:5001

# 터미널
python3 todo.py login               # STORAGE=supabase 면 먼저 로그인
python3 todo.py list
```

> **`todo.py list`가 "로그인이 필요합니다"로 끝나면 정상이다.** 현재 `.env`가
> `STORAGE=supabase`이고 세션이 없는 상태다. `todo.py login` 하거나,
> 로그인 없이 둘러보려면 `STORAGE=sqlite python3 todo.py list` 처럼
> 한 번만 덮어써서 실행한다.
>
> 마지막 세션에서 로그아웃했으므로 **다음 세션은 로그아웃 상태로 시작한다.**
> 계정: `doccaebi@gmail.com` (비밀번호는 재설정해서 바꾼 상태)

### 현재 `.env` 상태

```
STORAGE=supabase          # sqlite | supabase
PORT=5001                 # 5000은 macOS AirPlay가 점유 (아래 §7 참고)
DB_PATH=db/todo.db
FLASK_SECRET_KEY=<설정됨>
SUPABASE_URL=https://zocsvheggxbtczhdgple.supabase.co
SUPABASE_ANON_KEY=<sb_publishable_… 설정됨>
```

`STORAGE=supabase`면 **로그인이 필요**하다. 로그인 없이 쓰려면 `sqlite`로 바꾼다.
두 저장소는 서로 독립이라 데이터가 섞이지 않는다.

---

## 3. 구조 — 이게 이 프로젝트의 핵심이다

```
todoapp/
├── models.py            184줄  값 객체 + 입력 검증        ← 저장소를 모른다
├── keycheck.py           68줄  Supabase 키 종류 판정
├── config.py            124줄  .env 로딩 + service_role 가드
├── session.py            69줄  CLI 토큰 보관 (0600)
├── supabase_client.py   148줄  인증 (supabase-py에 위임)
├── auth_flow.py         140줄  로그인·가입·비밀번호 찾기 흐름
│
├── database.py           63줄  SQLite 커넥션·PRAGMA
├── repository.py        329줄  SQLite SQL 전담
├── stores/
│   ├── __init__.py      134줄  Store 프로토콜 + build_store()   ← 유일한 분기점
│   ├── sqlite_store.py   60줄  로컬 파일
│   └── supabase_store.py 326줄 클라우드 Postgres
│
├── service.py           183줄  유스케이스·트랜잭션 경계      ← CLI와 웹이 공유
├── cli.py               464줄  터미널 화면                  ← 저장소를 모른다
└── web/
    ├── __init__.py      135줄  Flask 팩토리 + 세션
    ├── routes.py        230줄  라우트 (PRG 패턴)
    └── templates/       6개    base · index · auth · reset ×3
```

### 지켜야 할 경계 3가지

1. **`cli.py`와 `web/`에 저장소 구현·SQL·`sqlite3`·`supabase`가 없다.**
   `tests/test_supabase_store.py::TestLayerBoundary`가 검사한다.
2. **`service.py`는 저장소 구현을 모른다.** `Store` 프로토콜만 안다.
3. **SQL은 `db/*.sql`과 `repository.py`·`supabase_store.py`에만 있다.**

> 이 경계를 지킨 덕에 SQLite → Supabase 이행에서 `models.py` · `db/schema.sql` ·
> `repository.py` · `database.py`를 **한 줄도 고치지 않았다.**

---

## 4. 기능

| 기능 | CLI | 웹 |
|---|---|---|
| 추가 / 목록 / 완료 / 삭제 | ✅ | ✅ |
| 마감일 (오늘까지·기한 지남 필터) | ✅ | ✅ |
| 태그 (N:M) | ✅ | ✅ |
| 제목·메모 검색 | ✅ | ✅ |
| 우선순위 (높음/보통/낮음) | ✅ | ✅ |
| 내용 수정 | ✅ | ❌ |
| 로그인 / 회원가입 / 로그아웃 | ✅ | ✅ |
| 비밀번호 찾기 | ✅ | ✅ |

### CLI 명령

```bash
python3 todo.py add "장보기" --due 내일 --tag 집안일 --priority high --notes "우유"
python3 todo.py list [--today|--overdue|--active|--done] [--tag X] [--search Y]
python3 todo.py done 3 / undone 3 / show 3 / rm 3 / edit 3 --due 없음
python3 todo.py tags
python3 todo.py signup / login / logout / whoami / reset-password
```

마감일 입력: `2026-09-10` · `오늘` · `내일` · `+7d` · `없음`
**지난 날짜는 `--due=-2d`** 처럼 등호로 붙여야 한다 (argparse가 옵션으로 오인).

### 웹 라우트

```
GET  /                          목록 (scope·tag·q 쿼리)
POST /todos                     추가
POST /todos/<id>/toggle         완료 토글
POST /todos/<id>/delete         삭제
GET  POST /login  /signup       로그인·가입
POST /logout
GET  POST /reset                비밀번호 찾기 1단계 (이메일)
GET  POST /reset/callback       2단계 (메일 링크가 돌아오는 자리)
```

---

## 5. DB 구조

두 저장소가 같은 모양이다. 다른 점은 §6에 정리했다.

```
todos ──< todo_tags >── tags
  1        N     N        1
```

| 표 | 주요 열 |
|---|---|
| `todos` | `id` `title` `notes` `is_done` `due_date` `priority` `created_at` `updated_at` `completed_at` |
| `tags` | `id` `name`(대소문자 무시 유일) `color` |
| `todo_tags` | `(todo_id, tag_id)` 복합 PK · 양쪽 CASCADE |

**정렬 기준(전 계층 공통)**: 미완료 먼저 → 마감일 있는 것 먼저 → 임박한 순 → 우선순위 → 등록순

파일: `db/schema.sql` (SQLite) · `db/supabase_schema.sql` (Postgres + RLS + RPC)
설계 근거: `docs/db-design.md`

### Supabase 쪽 추가 요소

| 종류 | 이름 |
|---|---|
| RLS 정책 3 | `todos_own` `tags_own` `todo_tags_own` — 전부 `user_id = auth.uid()` |
| 트리거 2 | `trg_todos_touch` `trg_todos_completed` |
| RPC 함수 3 | `upsert_tags` `create_todo_with_tags` `set_todo_tags` — 전부 `security invoker` |

---

## 6. 두 저장소의 차이 (건드릴 때 주의)

| 항목 | SQLite | Supabase |
|---|---|---|
| 태그 유일성 | `name` **전역** UNIQUE | **`(user_id, name)`** UNIQUE |
| 원자성 | `with conn:` 트랜잭션 | **RPC 함수** (PostgREST에 클라이언트 트랜잭션 없음) |
| `transaction()` | 실제 롤백 | **no-op** (원자성은 RPC가 담당) |
| 불리언 | `INTEGER 0/1` | 진짜 `boolean` |
| 날짜 | `TEXT 'YYYY-MM-DD'` | 진짜 `date` |
| LIKE 와일드카드 | `%` `_` | **`*`** · `or_()`는 **쉼표로 조건을 나눔** |
| `is not null` | `IS NOT NULL` | **`not_.is_(col,"null")`** (`is_(col,"not.null")`은 PGRST100 오류) |
| 로그인 | 없음 | 필요 |

> 새 기능을 추가할 때 **두 저장소 양쪽에 구현**하고, 위 차이를 각각 반영해야 한다.
> `Store` 프로토콜(`stores/__init__.py`)이 지켜야 할 표면을 정의한다.

---

## 7. 보안 모델

### 앱이 RLS를 우회할 방법이 없다

- **`service_role` 키를 어디에도 두지 않는다.** anon(공개) 키만 쓴다.
- 환경에 `SERVICE_ROLE` 이름의 변수가 있으면 **앱이 시작을 거부**한다
  (`config.assert_no_service_role()`).
- anon 키가 아닌 값(service_role · JWT Secret · URL 오입력)도 `config`가 거부한다.

### 2층 방어

```
1층  GRANT   어느 역할이 이 표에 손댈 수 있나  → anon에는 아무 권한도 없음
2층  RLS     그 역할이 어느 행을 볼 수 있나    → user_id = auth.uid() 인 행만
```

로그인 없이는 한 행도 읽히지 않고, 로그인해도 자기 행만 보인다.
`tests/test_supabase_integration.py`가 계정 2개로 실제 격리를 검증한다.

### 알려진 한계

| 항목 | 내용 |
|---|---|
| **CSRF 토큰 없음** | `127.0.0.1` 단독 실행 전제. 로그인이 생기면서 실제 위험이 됐다. **외부 노출 전에 Flask-WTF 필수** |
| 세션 파일 | `~/.config/todoapp/session.json` 권한 0600 |
| 메일 발송 | 무료 플랜 기본 SMTP는 **시간당 2통** + **프로젝트 팀원 주소로만** |
| 무료 플랜 | 1주 비활성 시 프로젝트 일시정지 (대시보드에서 Restore) |

---

## 8. 이 프로젝트를 만지기 전에 알아야 할 함정 6가지

실제로 부딪혀서 고친 것들이다. 같은 함정에 다시 빠지지 않게 적어둔다.

### ① SQLite `GLOB`에서 `_`는 와일드카드가 아니다

`LIKE` 문법이다. `CHECK (due_date GLOB '____-__-__')`는 정상 날짜를 전부 거부한다.
지금은 `date()` 왕복 비교로 실존 날짜까지 검증한다.

### ② SQLite는 외래키 검사가 기본 OFF다

커넥션마다 `PRAGMA foreign_keys = ON`이 필요하다. `database.connect()`가 처리한다.
`sqlite3 db/todo.db`로 직접 볼 때는 직접 켜야 CASCADE가 동작한다.

### ③ PostgREST의 와일드카드는 `*`, 조건 구분자는 쉼표다

이스케이프하지 않으면 `*` 검색이 전부 일치하고, `우유,계란` 검색이 필터를 쪼갠다.
`supabase_store.escape_postgrest_pattern()`이 처리한다.

### ④ `is_(col, "not.null")`은 PostgREST가 거부한다

`is.not.null` → PGRST100. 올바른 형태는 `not_.is_(col, "null")`.
**가짜 클라이언트 테스트로는 못 잡는다.** 실제 서버에 붙어야 드러난다.

### ⑤ argparse는 `-2d`를 옵션 이름으로 오인한다

`--due -2d`는 실패하고 `--due=-2d`는 된다.
**함수를 직접 부르는 테스트는 argparse를 우회하므로 이걸 못 잡는다.**

### ⑥ macOS AirPlay가 5000번을 상시 점유한다

`ControlCenter`가 `*:5000`과 `*:7000`을 잡는다 (`Server: AirTunes`).
Flask 기본 포트가 5000이라 정면 충돌한다. **그래서 이 앱은 5001을 쓴다.**

```
5000번:  localhost → AirPlay가 403 응답 (IPv6에 앉아 있어 폴백이 안 됨)
         127.0.0.1 → 우리 앱
5001번:  둘 다 우리 앱 ✅
```

포트를 바꾸려면 `.env`의 `PORT`와 **Supabase의 Site URL·Redirect URLs를 함께** 바꿔야 한다
(비밀번호 찾기 링크가 그 주소로 돌아온다).

---

## 9. 테스트 지도

새 기능을 넣을 때 어느 파일에 테스트를 추가할지 참고한다.

| 파일 | 개수 | 무엇을 검사하나 |
|---|---|---|
| `test_models.py` | 51 | 값 객체·입력 검증 (DB 없음) |
| `test_database.py` | 11 | 커넥션 PRAGMA·스키마 적용 |
| `test_repository_tags.py` | 14 | 태그 upsert (대소문자 무시) |
| `test_repository_todos.py` | 31 | 할 일 CRUD·태그 연결 |
| `test_repository_list.py` | 25 | 필터 조회 + **스키마 뷰 정합성** |
| `test_stores.py` | 16 | Store 이음새·트랜잭션 롤백 |
| `test_service.py` | 37 | 유스케이스·주입 시계 |
| `test_cli.py` | 59 | CLI 표 출력·상대 날짜 |
| `test_web.py` | 26 | 웹 라우트·PRG·이스케이프 |
| `test_auth_config.py` | 39 | 키 판정·service_role 가드·세션 0600 |
| `test_supabase_store.py` | 31 | PostgREST 요청 모양 (가짜 클라이언트) |
| `test_cli_auth.py` | 14 | CLI 로그인·저장소 선택 |
| `test_web_auth.py` | 16 | 웹 로그인 가드·세션 |
| `test_password_reset.py` | 41 | 비밀번호 찾기 (양쪽 경로) |
| `test_supabase_integration.py` | 23 | **실연결** CRUD + RLS 격리 + anon 차단 |
| **합계** | **434** | |

### 테스트 종류마다 잡는 버그가 다르다

| 방법 | 잡을 수 있는 것 | 못 잡는 것 |
|---|---|---|
| 유닛 (가짜 클라이언트) | 로직·검증·요청 모양 | 서버 문법 오류 (④) |
| 실연결 통합 | PostgREST 문법·RLS 실제 동작 | 네트워크 필요, 느림 |
| 직접 실행 | argparse·한글 정렬·눈에 보이는 것 (⑤) | 자동화 안 됨 |

> `test_supabase_integration.py`는 `.env`에 키가 없으면 **통째로 건너뛴다.**
> 다른 환경에서 받아도 나머지 411개는 그대로 돈다.

---

## 10. 문서 지도

| 파일 | 내용 |
|---|---|
| `README.md` | 설치·사용법·보안 범위 |
| `docs/db-design.md` | DB 설계 근거, SQLite 함정 |
| `docs/supabase-setup.md` | 클라우드 설정 절차 (키·스키마·URL·메일) |
| `plan.md` | 로컬 구현 계획 9단계 (STATUS: DONE) |
| `plan-supabase.md` | Supabase 이행 계획 6단계 (STATUS: DONE) |
| `HANDOFF.md` | **이 문서** |

외부 기록:
- 코드 · PR: <https://github.com/Lightnine999/aiffel_work>
- 학습 블로그 (2026-09-04): <https://lightnine999.github.io/blog_ggg/>

---

## 11. 남은 일

### 해야 할 것

- [ ] **Supabase `tasks` 표 정리** — 이 앱과 무관한 이전 실험 흔적.
      안에 할 일 1건("각 부서들 분류 후에 업무 분담")이 있어 **확인 후** 지우기로 보류했다.
      RLS가 걸려 있어 새는 데이터는 아니다.
      ```sql
      select * from public.tasks;                       -- 먼저 확인
      drop table if exists public.tasks cascade;         -- 그다음 삭제
      ```

### 해도 좋은 것

- [ ] **웹에 수정(edit) 화면** — CLI에는 있는데 웹에는 없다
- [ ] **커스텀 SMTP** (Resend 등 무료 티어) — 붙이면 팀원 아닌 사람에게도 메일이 가고
      메일 템플릿 수정이 열린다. 6자리 코드 방식 비밀번호 찾기도 가능해진다
- [ ] **CSRF (Flask-WTF)** — 외부 노출할 때 필수
- [ ] `tags` 삭제 기능 — `TagRepository.delete_unused()`는 있는데 화면에 노출 안 됨

### 하지 말아야 할 것

- ❌ `service_role` / `sb_secret_` / JWT Secret 키를 `.env`에 넣기
- ❌ RPC 함수를 `security definer`로 바꾸기 (RLS를 우회해버린다)
- ❌ `app.py`의 host를 `0.0.0.0`으로 바꾸기 (CSRF 없음)
- ❌ 포트를 5000으로 되돌리기 (AirPlay 충돌)
- ❌ 한쪽 저장소만 고치기 (§6 차이표 확인)

---

## 12. 다음 세션 시작 문구 예시

```
ToDoApp/HANDOFF.md 를 읽고 현재 상태를 파악해줘.
그리고 [하고 싶은 작업]을 진행하자.
```

작업 전에 이것만 돌려보면 상태가 확인된다.

```bash
cd /Users/kwonkwanggoo/aiffel_work/ToDoApp && \
  python3 -m pytest tests/ -q && python3 scripts/check_env.py --connect
```
