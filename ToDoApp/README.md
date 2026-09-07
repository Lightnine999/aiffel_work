# ToDoApp

할 일 관리 앱. **저장소를 두 가지 중에 고를 수 있다.**

| 저장소 | 설명 | 로그인 |
|---|---|---|
| `sqlite` | 내 컴퓨터의 파일 하나. 인터넷 불필요 | 없음 |
| `supabase` | 무료 클라우드 Postgres. 어느 기기에서든 같은 데이터 | 필요 |

같은 코어 위에 **터미널(CLI)** 과 **웹 화면(Flask)** 두 가지 인터페이스가 올라간다.
어느 쪽에서 바꿔도 같은 데이터를 보므로, 터미널에서 추가한 일이 웹에서 바로 보인다.
저장소를 바꿔도 화면 코드는 한 줄도 바뀌지 않는다.

## 기능

- 할 일 추가 / 목록 / 완료 표시 / 삭제 (CRUD)
- **클라우드 저장 + 행 수준 보안(RLS)** — 내 할 일은 나에게만 보인다
- **마감일** — 오늘까지·기한 지남 필터, 임박한 순 정렬
- **태그** — 하나의 할 일에 여러 태그, 태그로 필터
- 제목·메모 검색, 우선순위(높음/보통/낮음), 메모, 내용 수정

## 설치

```bash
cd ToDoApp
python3 -m pip install -r requirements-dev.txt
```

`.env.example`을 `.env`로 복사한 뒤, 아래 명령의 출력값을 `FLASK_SECRET_KEY`에 채운다.

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

`.env`가 없으면 웹 화면은 시작하지 않고 안내와 함께 멈춘다. CLI는 `.env` 없이도 돈다.

## 쓰는 법 — 터미널

```bash
python3 todo.py add "장보기" --due 내일 --tag 집안일 --priority high --notes "우유, 계란"
python3 todo.py list                # 전체
python3 todo.py list --today        # 오늘까지 마감인 미완료
python3 todo.py list --overdue      # 기한 지난 것
python3 todo.py list --tag 공부
python3 todo.py list --search 우유
python3 todo.py done 3              # 완료 표시
python3 todo.py undone 3            # 되돌리기
python3 todo.py show 3              # 상세
python3 todo.py edit 3 --due 없음   # 마감일 비우기
python3 todo.py rm 3                # 삭제 (확인 후)
python3 todo.py tags                # 태그 목록

# 클라우드(STORAGE=supabase)를 쓸 때만 필요
python3 todo.py signup              # 계정 만들기
python3 todo.py login               # 로그인 (비밀번호는 화면에 안 보이게 입력)
python3 todo.py whoami              # 현재 계정 확인
python3 todo.py logout
```

마감일 입력은 `2026-09-10` / `오늘` / `내일` / `+7d` / `없음`을 받는다.

**지난 날짜는 `--due=-2d` 처럼 등호로 붙여 쓴다.** `--due -2d`로 띄어 쓰면
`-2d`를 옵션 이름으로 오인해 사용법 오류가 난다(argparse의 표준 동작).

## 쓰는 법 — 웹 화면

```bash
python3 app.py
```

`http://127.0.0.1:5000` 을 브라우저에서 연다.

## 클라우드로 전환

1. `docs/supabase-setup.md` 절차를 따라 스키마를 적용한다
2. `.env`의 `STORAGE`를 `supabase`로 바꾼다
3. `python3 todo.py signup` 으로 계정을 만든다

되돌리려면 `STORAGE=sqlite`로 바꾸면 된다. 두 저장소는 서로 독립이라 데이터가 섞이지 않는다.

설정 확인:

```bash
python3 scripts/check_env.py --connect
```

## 구조

```
todoapp/models.py           값 객체 + 입력 검증      ← 저장소를 모른다
todoapp/service.py          유스케이스·트랜잭션      ← CLI와 웹이 공유
todoapp/stores/             저장소 이음새
  ├─ sqlite_store.py          로컬 파일
  └─ supabase_store.py        클라우드 Postgres
todoapp/database.py         SQLite 커넥션·PRAGMA
todoapp/repository.py       SQLite SQL 전담
todoapp/supabase_client.py  인증 (supabase-py에 위임)
todoapp/session.py          CLI 토큰 보관 (0600)
todoapp/cli.py              터미널 화면            ← 저장소를 모른다
todoapp/web/                Flask 화면             ← 같음
```

`cli.py`와 `web/`에 저장소 구현·SQL·`sqlite3`·`supabase` 가 없다는 것을 테스트가 검사한다.

DB 설계는 [docs/db-design.md](docs/db-design.md), 클라우드 설정은
[docs/supabase-setup.md](docs/supabase-setup.md), 구현 계획은
[plan.md](plan.md) / [plan-supabase.md](plan-supabase.md).

## 테스트

```bash
python3 -m pytest tests/ -q                                    # 전체
python3 -m pytest tests/ -q --ignore=tests/test_supabase_integration.py  # 네트워크 없이
```

로컬 테스트는 임시 DB(`tmp_path`)를 쓴다. 실제 `db/todo.db`를 건드리지 않는다.
통합 테스트는 `.env`에 Supabase 키가 없으면 통째로 건너뛴다.

## 보안 범위 (읽고 넘어가세요)

### 클라우드 저장소 (`STORAGE=supabase`)

**앱이 RLS를 우회할 방법이 없다.** 이게 이 설계의 핵심이다.

- `service_role` 키를 어디에도 두지 않는다. anon(공개) 키만 쓴다.
  환경에 `SERVICE_ROLE` 이름의 변수가 있으면 앱이 시작을 거부한다.
- 보안이 2층이다. **GRANT**가 "어느 역할이 표에 손대나"를, **RLS**가
  "그 역할이 어느 행을 보나"를 정한다. anon에는 아무 권한도 주지 않았다.
- 그래서 로그인 없이는 한 행도 읽히지 않고, 로그인해도 자기 행만 보인다.
  **테스트로 증명한다** — `tests/test_supabase_integration.py`가 계정 B로
  계정 A의 행을 읽기·수정·삭제 시도하고 전부 실패하는지 확인한다.
- 원자성이 필요한 작업(할 일 + 태그)은 Postgres 함수로 처리한다. 전부
  `security invoker`다 — `definer`로 만들면 RLS를 통과해 버린다.
- 비밀번호는 Supabase가 관리한다. 이 앱은 저장하지 않는다.
- CLI 토큰은 `~/.config/todoapp/session.json`에 **파일 권한 0600**으로 둔다.

### 로컬 저장소 (`STORAGE=sqlite`)

로그인이 없다. 계정 개념 자체가 없으므로 RLS도 없다. **로컬 단독 실행 전제**다.

### 두 경우 모두

- **CSRF 토큰이 없다.** `127.0.0.1` 단독 실행 전제다. 외부에 노출하거나
  여러 사람이 쓰게 만들려면 Flask-WTF로 CSRF를 붙여야 한다.
  로그인이 생기면서 이건 실제 위험이 됐다 — 노출 전에 반드시 처리할 것.
- `app.py`의 host를 `0.0.0.0`으로 바꾸지 말 것.
- 비밀값은 `.env`에만 둔다. `.env`와 `*.db`는 `.gitignore`에 등록되어 있다.

## 알아둘 것 하나 (SQLite 함정)

**SQLite는 외래키 검사가 기본으로 꺼져 있다.** 커넥션마다 켜야 한다.
`todoapp/database.py`의 `connect()`가 이걸 처리하므로 앱 코드는 신경 쓸 필요 없지만,
`sqlite3 db/todo.db`로 직접 들여다볼 때는 아래를 먼저 실행해야 CASCADE가 동작한다.

```sql
PRAGMA foreign_keys = ON;
```

## 도구

Python 3.13 / 표준 `sqlite3` / Flask / Supabase(무료 플랜) / pytest / python-dotenv — 전부 무료.
