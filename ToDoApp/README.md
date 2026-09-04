# ToDoApp

내 컴퓨터에서만 도는 할 일 관리 앱. 데이터는 로컬 SQLite 파일 하나에 저장된다.
같은 코어 위에 **터미널(CLI)** 과 **웹 화면(Flask)** 두 가지 인터페이스가 올라간다.
어느 쪽에서 바꿔도 같은 DB를 보므로, 터미널에서 추가한 일이 웹에서 바로 보인다.

## 기능

- 할 일 추가 / 목록 / 완료 표시 / 삭제 (CRUD)
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
```

마감일 입력은 `2026-09-10` / `오늘` / `내일` / `+7d` / `없음`을 받는다.

**지난 날짜는 `--due=-2d` 처럼 등호로 붙여 쓴다.** `--due -2d`로 띄어 쓰면
`-2d`를 옵션 이름으로 오인해 사용법 오류가 난다(argparse의 표준 동작).

## 쓰는 법 — 웹 화면

```bash
python3 app.py
```

`http://127.0.0.1:5000` 을 브라우저에서 연다.

## 구조

```
todoapp/models.py      값 객체 + 입력 검증   ← DB를 모른다
todoapp/database.py    커넥션·PRAGMA·스키마
todoapp/repository.py  SQL 전담              ← SQL은 여기와 db/schema.sql에만 있다
todoapp/service.py     유스케이스·트랜잭션   ← CLI와 웹이 공유
todoapp/cli.py         터미널 화면           ← SQL도 sqlite3도 모른다
todoapp/web/           Flask 화면            ← 같음
```

DB 설계와 근거는 [docs/db-design.md](docs/db-design.md), 구현 계획은 [plan.md](plan.md).

## 테스트

```bash
python3 -m pytest tests/ -q
```

모든 테스트는 임시 DB(`tmp_path`)를 쓴다. 실제 `db/todo.db`를 건드리지 않는다.

## 보안 범위 (읽고 넘어가세요)

이 앱은 **로컬 단독 실행 전제**다. 로그인이 없고, 따라서 CSRF 토큰도 세션 보호도 없다.

- `app.py`의 host를 `0.0.0.0`으로 바꾸거나 외부에 노출하지 말 것.
- 여러 사람이 쓰게 만들려면 로그인을 **직접 구현하지 말고** Flask-Login +
  Flask-WTF(CSRF)를 붙인다.
- 비밀값은 `.env`에만 둔다. `.env`와 `*.db`는 `.gitignore`에 등록되어 있다.

## 알아둘 것 하나 (SQLite 함정)

**SQLite는 외래키 검사가 기본으로 꺼져 있다.** 커넥션마다 켜야 한다.
`todoapp/database.py`의 `connect()`가 이걸 처리하므로 앱 코드는 신경 쓸 필요 없지만,
`sqlite3 db/todo.db`로 직접 들여다볼 때는 아래를 먼저 실행해야 CASCADE가 동작한다.

```sql
PRAGMA foreign_keys = ON;
```

## 도구

Python 3.13 / 표준 `sqlite3` / Flask / pytest / python-dotenv — 전부 무료.
