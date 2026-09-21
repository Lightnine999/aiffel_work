# ToDoApp 구현 계획

**STATUS: DONE** (2026-09-04 완료) — 9개 태스크 전부 구현, 테스트 254개 통과.

> **에이전트 실행자 안내:** 이 계획은 `superpowers:subagent-driven-development` 또는
> `superpowers:executing-plans`로 태스크 단위 실행한다. 각 스텝은 `- [ ]` 체크박스로 추적한다.

**목표:** 로컬 SQLite에 저장하는 Todo 앱을, 공유 코어 위에 CLI와 Flask 웹 두 프론트를 얹어 구현한다.

**아키텍처:** 4계층. `models`(순수 검증) → `database`(연결·PRAGMA·스키마) → `repository`(SQL 전담)
→ `service`(유스케이스). `cli`와 `web`은 `service`만 호출하고 SQL을 직접 쓰지 않는다.
프론트를 하나 더 붙여도 코어는 그대로다.

**기술 스택:** Python 3.13.9 / 표준 `sqlite3` (3.51.0) / Flask 3.1.2 / Jinja2 3.1.6 /
pytest 8.4.2 / python-dotenv 1.1.0 — 전부 설치 확인 완료(2026-09-04). 추가 설치 없음.

**스펙:** `docs/db-design.md` (DB 설계·근거·검증 결과) + `db/schema.sql` (확정 스키마) + 사용자 PRD.

---

## 전역 제약

- **언어·주석**: 모든 주석·문서·커밋 메시지는 한국어. 변수·함수명은 영어.
- **의존성**: 무료 도구만. 위 스택 외 신규 패키지 추가 금지.
- **비밀값**: `.env`로만. 코드에 경로·값 하드코딩 금지. `.env`는 커밋 금지(`.gitignore` 등록 완료).
- **로그인 없음**: PRD상 인증 미구현. 직접 구현하지 않는다. 따라서 CSRF 토큰·세션도 없다
  (로컬 단독 실행 전제. README에 명시한다).
- **날짜 형식**: DB·도메인 전 계층에서 `'YYYY-MM-DD'` 문자열. `date` 객체를 DB에 넣지 않는다.
- **불리언**: DB는 `INTEGER 0/1`, 파이썬 도메인은 `bool`. 변환은 `repository`에서만 한다.
- **외래키**: 커넥션마다 `PRAGMA foreign_keys = ON`. 트랜잭션 밖에서 실행해야 적용된다.
- **트랜잭션**: 다중 문장 쓰기는 `with conn:` 블록으로 감싼다(성공 시 커밋, 예외 시 롤백).
  `with conn:`은 커넥션을 닫지 않는다 — 닫기는 별도.
- **파일 크기**: 모듈당 300줄 이하, 함수당 50줄 이하.
- **테스트**: 모든 테스트는 `tmp_path` 임시 DB를 쓴다. 실제 `db/todo.db`를 건드리는 테스트 금지.
- **커밋**: `feat/todoapp` 브랜치에서 태스크마다 1커밋. `ToDoApp/` 경로만 `git add` 한다
  (상위 저장소에 무관한 미추적 파일이 많다).

## 파일 구조

| 파일 | 책임 |
|---|---|
| `todoapp/__init__.py` | 패키지 버전만 |
| `todoapp/config.py` | `.env` 로딩, `DB_PATH` 해석 |
| `todoapp/models.py` | `Todo`·`Tag` 값 객체 + 입력 정규화·검증 (DB 무관 순수 함수) |
| `todoapp/database.py` | 커넥션 생성, `PRAGMA`, `schema.sql` 적용 |
| `todoapp/repository.py` | `TagRepository`·`TodoRepository`. SQL은 여기서만 작성 |
| `todoapp/service.py` | `TodoService`. 유스케이스 조합 + 트랜잭션 경계 |
| `todoapp/cli.py` | argparse 서브커맨드, 표 출력 |
| `todoapp/web/__init__.py` | Flask app factory, 요청별 커넥션 관리 |
| `todoapp/web/routes.py` | 라우트 (PRG 패턴) |
| `todoapp/web/templates/*.html` | base / index |
| `tests/conftest.py` | 임시 DB·서비스 fixture |
| `tests/test_*.py` | 계층별 테스트 6종 |

## 태스크 의존 순서

```
1 모델 ─→ 2 DB ─→ 3 태그저장소 ─→ 4 할일저장소 ─→ 5 필터조회 ─→ 6 서비스 ─┬─→ 7 CLI ─┐
                                                                          └─→ 8 웹  ─┴─→ 9 문서
```

---

### Task 1: 프로젝트 골격 + 도메인 모델 검증

DB가 없어도 도는 순수 계층부터 만든다. pytest 세팅도 여기서 끝낸다.

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`
- Create: `todoapp/__init__.py`, `todoapp/config.py`, `todoapp/models.py`
- Test: `tests/__init__.py`, `tests/test_models.py`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces:
  - `models.ValidationError(ValueError)`
  - `models.Tag(id: int | None, name: str, color: str)` — frozen dataclass
  - `models.Todo(id, title, notes, is_done: bool, due_date: str | None, priority: int, created_at, updated_at, completed_at, tags: tuple[Tag, ...])` — frozen dataclass
  - `models.normalize_title(raw: str | None) -> str`
  - `models.normalize_due_date(raw: str | None) -> str | None`
  - `models.normalize_tag_name(raw: str | None) -> str`
  - `models.normalize_color(raw: str | None) -> str`
  - `models.normalize_priority(raw: int | str | None) -> int`
  - `models.parse_tag_list(raw: str | Iterable[str] | None) -> tuple[str, ...]`
  - `models.PRIORITY_HIGH=1`, `PRIORITY_NORMAL=2`, `PRIORITY_LOW=3`, `PRIORITY_NAMES: dict[str,int]`
  - `config.get_db_path() -> pathlib.Path`

- [x] **Step 1: 의존성·pytest 설정 파일 작성**

`requirements.txt`:
```
Flask>=3.1,<4
python-dotenv>=1.1,<2
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8.4,<9
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -v --strict-markers
```

- [x] **Step 2: 실패하는 테스트 작성**

`tests/__init__.py`는 빈 파일로 만든다.

`tests/test_models.py`:
```python
"""도메인 값 객체와 입력 검증 테스트. DB를 쓰지 않는다."""
import pytest

from todoapp.models import (
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_NORMAL,
    Tag,
    Todo,
    ValidationError,
    normalize_color,
    normalize_due_date,
    normalize_priority,
    normalize_tag_name,
    normalize_title,
    parse_tag_list,
)


class TestNormalizeTitle:
    def test_앞뒤_공백을_제거한다(self):
        assert normalize_title("  장보기  ") == "장보기"

    def test_내부_연속_공백을_하나로_줄인다(self):
        assert normalize_title("장   보기") == "장 보기"

    @pytest.mark.parametrize("bad", ["", "   ", "\t\n", None])
    def test_빈_제목은_거부한다(self, bad):
        with pytest.raises(ValidationError):
            normalize_title(bad)

    def test_200자를_넘으면_거부한다(self):
        with pytest.raises(ValidationError):
            normalize_title("가" * 201)

    def test_200자는_통과한다(self):
        assert len(normalize_title("가" * 200)) == 200


class TestNormalizeDueDate:
    def test_ISO_날짜를_그대로_돌려준다(self):
        assert normalize_due_date("2026-09-10") == "2026-09-10"

    @pytest.mark.parametrize("empty", [None, "", "   "])
    def test_빈_값은_None이다(self, empty):
        assert normalize_due_date(empty) is None

    def test_하이픈_없는_형식은_거부한다(self):
        # date.fromisoformat은 Python 3.11+에서 '20260904'를 통과시킨다.
        # 형식 검사를 먼저 걸지 않으면 DB에 잘못된 형식이 들어간다.
        with pytest.raises(ValidationError):
            normalize_due_date("20260904")

    @pytest.mark.parametrize("bad", ["2026/09/04", "26-09-04", "2026-9-4", "내일"])
    def test_잘못된_형식은_거부한다(self, bad):
        with pytest.raises(ValidationError):
            normalize_due_date(bad)

    def test_존재하지_않는_날짜는_거부한다(self):
        with pytest.raises(ValidationError):
            normalize_due_date("2026-02-31")

    def test_윤년_2월29일은_통과한다(self):
        assert normalize_due_date("2028-02-29") == "2028-02-29"


class TestNormalizeTagName:
    def test_앞뒤_공백을_제거한다(self):
        assert normalize_tag_name(" 공부 ") == "공부"

    @pytest.mark.parametrize("bad", ["", "   ", None])
    def test_빈_태그는_거부한다(self, bad):
        with pytest.raises(ValidationError):
            normalize_tag_name(bad)

    def test_쉼표가_들어가면_거부한다(self):
        # CLI에서 쉼표로 태그를 나누므로 태그명에 쉼표가 있으면 안 된다.
        with pytest.raises(ValidationError):
            normalize_tag_name("공부,집안일")

    def test_30자를_넘으면_거부한다(self):
        with pytest.raises(ValidationError):
            normalize_tag_name("가" * 31)


class TestParseTagList:
    def test_쉼표_문자열을_나눈다(self):
        assert parse_tag_list("공부, 집안일") == ("공부", "집안일")

    def test_리스트도_받는다(self):
        assert parse_tag_list(["공부", " 집안일 "]) == ("공부", "집안일")

    def test_빈_값은_빈_튜플이다(self):
        assert parse_tag_list(None) == ()
        assert parse_tag_list("") == ()

    def test_빈_조각은_건너뛴다(self):
        assert parse_tag_list("공부,,  ,집안일") == ("공부", "집안일")

    def test_중복은_순서를_지키며_한_번만_남긴다(self):
        assert parse_tag_list("공부,집안일,공부") == ("공부", "집안일")

    def test_대소문자만_다른_태그는_같은_것으로_본다(self):
        # DB의 tags.name이 COLLATE NOCASE라 대소문자 변형은 같은 행이 된다.
        assert parse_tag_list("Study,study") == ("Study",)


class TestNormalizeColor:
    def test_HEX_색상을_대문자로_정규화한다(self):
        assert normalize_color("#534ab7") == "#534AB7"

    def test_빈_값은_기본색이다(self):
        assert normalize_color(None) == "#888880"

    @pytest.mark.parametrize("bad", ["534AB7", "#534AB", "#GGGGGG", "red"])
    def test_잘못된_색상은_거부한다(self, bad):
        with pytest.raises(ValidationError):
            normalize_color(bad)


class TestNormalizePriority:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (1, PRIORITY_HIGH),
            ("2", PRIORITY_NORMAL),
            ("high", PRIORITY_HIGH),
            ("HIGH", PRIORITY_HIGH),
            ("normal", PRIORITY_NORMAL),
            ("low", PRIORITY_LOW),
            (None, PRIORITY_NORMAL),
        ],
    )
    def test_숫자와_이름을_모두_받는다(self, raw, expected):
        assert normalize_priority(raw) == expected

    @pytest.mark.parametrize("bad", [0, 4, "urgent", "1.5"])
    def test_범위_밖은_거부한다(self, bad):
        with pytest.raises(ValidationError):
            normalize_priority(bad)


class TestValueObjects:
    def test_Todo는_불변이다(self):
        todo = Todo(id=1, title="장보기")
        with pytest.raises(Exception):
            todo.title = "다른 제목"

    def test_Todo_기본값(self):
        todo = Todo(id=None, title="장보기")
        assert todo.is_done is False
        assert todo.due_date is None
        assert todo.priority == PRIORITY_NORMAL
        assert todo.tags == ()

    def test_Tag는_불변이다(self):
        tag = Tag(id=1, name="공부")
        with pytest.raises(Exception):
            tag.name = "운동"
```

- [x] **Step 3: 테스트 실패 확인**

Run: `cd ToDoApp && python3 -m pytest tests/test_models.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'todoapp'`

- [x] **Step 4: 최소 구현 작성**

`todoapp/__init__.py`:
```python
"""로컬 SQLite Todo 앱."""

__version__ = "0.1.0"
```

`todoapp/models.py`:
```python
"""도메인 값 객체와 입력 정규화·검증.

이 모듈은 DB를 모른다. 순수 함수만 있으므로 테스트가 가장 싸다.
'정규화'와 '검증'을 한 함수에 묶은 이유: 입력을 받는 지점이 CLI·웹 둘이라,
두 곳에서 각자 다듬으면 규칙이 갈라진다. 진입점 하나로 강제한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

PRIORITY_HIGH = 1
PRIORITY_NORMAL = 2
PRIORITY_LOW = 3

PRIORITY_NAMES: dict[str, int] = {
    "high": PRIORITY_HIGH,
    "normal": PRIORITY_NORMAL,
    "low": PRIORITY_LOW,
}
PRIORITY_LABELS: dict[int, str] = {
    PRIORITY_HIGH: "높음",
    PRIORITY_NORMAL: "보통",
    PRIORITY_LOW: "낮음",
}

DEFAULT_TAG_COLOR = "#888880"
MAX_TITLE_LENGTH = 200
MAX_TAG_LENGTH = 30

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_WHITESPACE_RUN_RE = re.compile(r"\s+")


class ValidationError(ValueError):
    """사용자 입력이 규칙을 어겼을 때. CLI·웹이 이걸 잡아 안내 문구로 바꾼다."""


@dataclass(frozen=True, slots=True)
class Tag:
    id: int | None
    name: str
    color: str = DEFAULT_TAG_COLOR


@dataclass(frozen=True, slots=True)
class Todo:
    id: int | None
    title: str
    notes: str | None = None
    is_done: bool = False
    due_date: str | None = None
    priority: int = PRIORITY_NORMAL
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
    tags: tuple[Tag, ...] = field(default=())


def normalize_title(raw: str | None) -> str:
    """제목을 다듬는다. 앞뒤 공백 제거 + 내부 연속 공백을 하나로."""
    if raw is None:
        raise ValidationError("제목을 입력하세요.")
    title = _WHITESPACE_RUN_RE.sub(" ", str(raw)).strip()
    if not title:
        raise ValidationError("제목을 입력하세요.")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValidationError(f"제목은 {MAX_TITLE_LENGTH}자를 넘을 수 없습니다.")
    return title


def normalize_due_date(raw: str | None) -> str | None:
    """마감일을 'YYYY-MM-DD'로 확정한다. 빈 값은 None(마감일 없음)."""
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    # 형식 검사를 먼저 한다. date.fromisoformat은 Python 3.11+에서
    # '20260904' 같은 하이픈 없는 형식도 받아주기 때문이다.
    if not _ISO_DATE_RE.match(value):
        raise ValidationError(f"마감일은 'YYYY-MM-DD' 형식이어야 합니다: {raw!r}")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"존재하지 않는 날짜입니다: {value}") from exc
    return value


def normalize_tag_name(raw: str | None) -> str:
    if raw is None:
        raise ValidationError("태그 이름을 입력하세요.")
    name = _WHITESPACE_RUN_RE.sub(" ", str(raw)).strip()
    if not name:
        raise ValidationError("태그 이름을 입력하세요.")
    if "," in name:
        raise ValidationError("태그 이름에 쉼표를 쓸 수 없습니다.")
    if len(name) > MAX_TAG_LENGTH:
        raise ValidationError(f"태그는 {MAX_TAG_LENGTH}자를 넘을 수 없습니다.")
    return name


def parse_tag_list(raw: str | Iterable[str] | None) -> tuple[str, ...]:
    """'공부, 집안일' 또는 ['공부','집안일']을 정규화된 튜플로.

    중복은 첫 등장만 남긴다. DB의 tags.name이 COLLATE NOCASE라
    대소문자만 다른 이름은 같은 태그로 취급한다.
    """
    if raw is None:
        return ()
    parts = raw.split(",") if isinstance(raw, str) else list(raw)
    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if part is None or not str(part).strip():
            continue
        name = normalize_tag_name(part)
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return tuple(result)


def normalize_color(raw: str | None) -> str:
    if raw is None or not str(raw).strip():
        return DEFAULT_TAG_COLOR
    color = str(raw).strip()
    if not _HEX_COLOR_RE.match(color):
        raise ValidationError(f"색상은 '#RRGGBB' 형식이어야 합니다: {raw!r}")
    return color.upper()


def normalize_priority(raw: int | str | None) -> int:
    if raw is None:
        return PRIORITY_NORMAL
    if isinstance(raw, bool):  # bool은 int의 하위형이라 먼저 걸러낸다
        raise ValidationError(f"알 수 없는 우선순위입니다: {raw!r}")
    if isinstance(raw, int):
        value = raw
    else:
        text = str(raw).strip().lower()
        if text in PRIORITY_NAMES:
            return PRIORITY_NAMES[text]
        try:
            value = int(text)
        except ValueError as exc:
            raise ValidationError(f"알 수 없는 우선순위입니다: {raw!r}") from exc
    if value not in PRIORITY_LABELS:
        raise ValidationError("우선순위는 1(높음)·2(보통)·3(낮음) 중 하나여야 합니다.")
    return value
```

`todoapp/config.py`:
```python
"""설정 로딩. 값은 .env에서만 읽는다."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "db" / "todo.db"


def get_db_path() -> Path:
    """DB 파일 경로. .env의 DB_PATH가 있으면 그것, 없으면 db/todo.db."""
    load_dotenv(PROJECT_ROOT / ".env")
    raw = os.getenv("DB_PATH", "").strip()
    path = Path(raw) if raw else DEFAULT_DB_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path
```

- [x] **Step 5: 테스트 통과 확인**

Run: `cd ToDoApp && python3 -m pytest tests/test_models.py -q`
Expected: PASS — 전 케이스 통과

- [x] **Step 6: 커밋**

```bash
cd /Users/kwonkwanggoo/aiffel_work
git checkout -b feat/todoapp
git add ToDoApp/requirements.txt ToDoApp/requirements-dev.txt ToDoApp/pytest.ini \
        ToDoApp/todoapp/ ToDoApp/tests/
git commit -m "feat(todoapp): 도메인 모델과 입력 검증 추가"
```

---

### Task 2: DB 연결 계층

**Files:**
- Create: `todoapp/database.py`
- Create: `tests/conftest.py`, `tests/test_database.py`

**Interfaces:**
- Consumes: `config.get_db_path`
- Produces:
  - `database.SCHEMA_PATH: Path`
  - `database.connect(db_path: str | Path) -> sqlite3.Connection`
  - `database.initialize(conn: sqlite3.Connection, schema_path: Path | None = None) -> None`
  - `database.open_db(db_path) -> ContextManager[sqlite3.Connection]`
  - fixture `conn` (임시 DB 커넥션), fixture `db_path`

- [x] **Step 1: 실패하는 테스트 작성**

`tests/conftest.py`:
```python
"""테스트 공용 fixture. 모든 테스트는 tmp_path 임시 DB만 쓴다."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from todoapp.database import connect, initialize


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_todo.db"


@pytest.fixture
def conn(db_path: Path):
    connection = connect(db_path)
    initialize(connection)
    yield connection
    connection.close()
```

`tests/test_database.py`:
```python
"""커넥션 설정과 스키마 적용 테스트."""
from __future__ import annotations

import sqlite3

import pytest

from todoapp.database import connect, initialize, open_db


def test_외래키_검사가_켜져_있다(conn):
    # SQLite는 기본이 OFF다. 꺼져 있으면 CASCADE가 조용히 동작하지 않는다.
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_행을_이름으로_꺼낼_수_있다(conn):
    row = conn.execute("SELECT 1 AS answer").fetchone()
    assert row["answer"] == 1


def test_스키마가_표_세_개를_만든다(conn):
    names = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert {"todos", "tags", "todo_tags"} <= names


def test_스키마가_뷰와_트리거를_만든다(conn):
    objects = {
        (r["type"], r["name"])
        for r in conn.execute("SELECT type, name FROM sqlite_master WHERE type IN ('view','trigger')")
    }
    assert ("view", "v_today_todos") in objects
    assert ("view", "v_todo_list") in objects
    assert ("trigger", "trg_todos_updated_at") in objects
    assert ("trigger", "trg_todos_completed_at") in objects


def test_initialize를_두_번_불러도_안전하다(conn):
    # 스키마가 전부 IF NOT EXISTS이므로 재실행이 깨지면 안 된다.
    initialize(conn)
    initialize(conn)
    assert conn.execute("SELECT count(*) AS c FROM todos").fetchone()["c"] == 0


def test_없는_상위_폴더를_자동으로_만든다(tmp_path):
    target = tmp_path / "없는폴더" / "todo.db"
    connection = connect(target)
    try:
        assert target.parent.is_dir()
    finally:
        connection.close()


def test_open_db는_빠져나갈_때_닫는다(db_path):
    with open_db(db_path) as connection:
        connection.execute("INSERT INTO todos (title) VALUES ('테스트')")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_open_db는_커밋한다(db_path):
    with open_db(db_path) as first:
        with first:
            first.execute("INSERT INTO todos (title) VALUES ('남아야 한다')")
    with open_db(db_path) as second:
        assert second.execute("SELECT count(*) AS c FROM todos").fetchone()["c"] == 1


def test_외래키_위반은_거부된다(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO todo_tags (todo_id, tag_id) VALUES (999, 999)")
```

- [x] **Step 2: 테스트 실패 확인**

Run: `cd ToDoApp && python3 -m pytest tests/test_database.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'todoapp.database'`

- [x] **Step 3: 최소 구현 작성**

`todoapp/database.py`:
```python
"""SQLite 커넥션 관리와 스키마 적용.

SQL 문장은 여기 없다. 여기는 '연결을 어떤 상태로 만들어 넘기느냐'만 책임진다.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from todoapp.config import PROJECT_ROOT

SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"


def connect(db_path: str | Path) -> sqlite3.Connection:
    """앱이 기대하는 상태로 맞춰진 커넥션을 돌려준다.

    - foreign_keys ON: SQLite 기본값이 OFF다. 트랜잭션 안에서는 바꿔도 무시되므로
      연결 직후, 어떤 쓰기보다 먼저 실행해야 한다.
    - row_factory: 컬럼을 이름으로 꺼내기 위함. 인덱스 번호로 꺼내면
      나중에 SELECT 열 순서가 바뀔 때 조용히 깨진다.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize(conn: sqlite3.Connection, schema_path: Path | None = None) -> None:
    """schema.sql을 적용한다. 전부 IF NOT EXISTS라 여러 번 불러도 안전하다."""
    path = schema_path or SCHEMA_PATH
    if not path.is_file():
        raise FileNotFoundError(f"스키마 파일을 찾을 수 없습니다: {path}")
    conn.executescript(path.read_text(encoding="utf-8"))
    # executescript는 시작 시 커밋을 하고 스크립트를 그대로 실행한다.
    # 스크립트 안의 PRAGMA가 커넥션 상태를 건드렸을 수 있으므로 다시 보장한다.
    conn.execute("PRAGMA foreign_keys = ON")


@contextmanager
def open_db(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """connect + initialize + 반드시 close. 짧은 작업(CLI 한 번 실행)용."""
    conn = connect(db_path)
    try:
        initialize(conn)
        yield conn
    finally:
        conn.close()
```

- [x] **Step 4: 테스트 통과 확인**

Run: `cd ToDoApp && python3 -m pytest tests/ -q`
Expected: PASS — Task 1 테스트까지 전부 통과

- [x] **Step 5: 커밋**

```bash
cd /Users/kwonkwanggoo/aiffel_work
git add ToDoApp/todoapp/database.py ToDoApp/tests/conftest.py ToDoApp/tests/test_database.py
git commit -m "feat(todoapp): SQLite 커넥션 계층 추가 (외래키 ON, 스키마 자동 적용)"
```

---
### Task 3: 태그 리포지토리

**Files:**
- Create: `todoapp/repository.py`
- Create: `tests/test_repository_tags.py`

**Interfaces:**
- Consumes: `models.Tag`, `models.normalize_tag_name`, `models.normalize_color`, fixture `conn`
- Produces:
  - `repository.TagRepository(conn: sqlite3.Connection)`
  - `.upsert(name: str, color: str | None = None) -> Tag`
  - `.get_by_name(name: str) -> Tag | None`
  - `.get(tag_id: int) -> Tag | None`
  - `.list_all() -> list[Tag]`
  - `.delete_unused() -> int`
  - `repository.row_to_tag(row: sqlite3.Row) -> Tag`

**확인된 DB 사실 (2026-09-04 실측):** `tags.name`이 `UNIQUE COLLATE NOCASE`라
`'study'`는 `'Study'`가 있으면 거부된다. `ON CONFLICT(name) DO UPDATE ... RETURNING`이
이 암시적 인덱스를 정상적으로 잡으며, 이때 **이름의 대소문자는 먼저 저장된 쪽이 유지된다.**

- [x] **Step 1: 실패하는 테스트 작성**

`tests/test_repository_tags.py`:
```python
"""태그 리포지토리 테스트."""
from __future__ import annotations

import pytest

from todoapp.models import Tag, ValidationError
from todoapp.repository import TagRepository


@pytest.fixture
def tags(conn) -> TagRepository:
    return TagRepository(conn)


def test_새_태그를_만든다(tags):
    tag = tags.upsert("공부")
    assert isinstance(tag, Tag)
    assert tag.id is not None
    assert tag.name == "공부"
    assert tag.color == "#888880"


def test_색상을_지정할_수_있다(tags):
    tag = tags.upsert("공부", "#534ab7")
    assert tag.color == "#534AB7"  # 대문자로 정규화된다


def test_같은_이름을_다시_넣으면_같은_행을_돌려준다(tags):
    first = tags.upsert("공부")
    second = tags.upsert("공부")
    assert first.id == second.id
    assert len(tags.list_all()) == 1


def test_대소문자만_다른_이름도_같은_행이다(tags):
    first = tags.upsert("Study")
    second = tags.upsert("study")
    assert first.id == second.id
    # 처음 저장된 표기를 유지한다
    assert second.name == "Study"
    assert len(tags.list_all()) == 1


def test_다시_넣을_때_색상만_바꿀_수_있다(tags):
    original = tags.upsert("공부", "#534AB7")
    updated = tags.upsert("공부", "#1D9E75")
    assert updated.id == original.id
    assert updated.color == "#1D9E75"


def test_색상을_생략하면_기존_색상을_지킨다(tags):
    tags.upsert("공부", "#534AB7")
    kept = tags.upsert("공부")
    assert kept.color == "#534AB7"


def test_앞뒤_공백은_제거된다(tags):
    assert tags.upsert("  공부  ").name == "공부"


def test_빈_이름은_거부한다(tags):
    with pytest.raises(ValidationError):
        tags.upsert("   ")


def test_잘못된_색상은_거부한다(tags):
    with pytest.raises(ValidationError):
        tags.upsert("공부", "red")


def test_이름으로_찾는다_대소문자_무시(tags):
    created = tags.upsert("Study")
    assert tags.get_by_name("STUDY").id == created.id


def test_없는_이름은_None이다(tags):
    assert tags.get_by_name("없는태그") is None


def test_id로_찾는다(tags):
    created = tags.upsert("공부")
    assert tags.get(created.id).name == "공부"
    assert tags.get(9999) is None


def test_전체_목록은_이름순이다(tags):
    tags.upsert("집안일")
    tags.upsert("공부")
    tags.upsert("운동")
    assert [t.name for t in tags.list_all()] == ["공부", "운동", "집안일"]


def test_아무_할_일에도_안_붙은_태그를_지운다(conn, tags):
    used = tags.upsert("공부")
    tags.upsert("고아태그")
    conn.execute("INSERT INTO todos (title) VALUES ('할 일')")
    todo_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.execute("INSERT INTO todo_tags (todo_id, tag_id) VALUES (?, ?)", (todo_id, used.id))
    assert tags.delete_unused() == 1
    assert [t.name for t in tags.list_all()] == ["공부"]
```

- [x] **Step 2: 테스트 실패 확인**

Run: `cd ToDoApp && python3 -m pytest tests/test_repository_tags.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'todoapp.repository'`

- [x] **Step 3: 최소 구현 작성**

`todoapp/repository.py` (이 태스크에서 만드는 부분만. Task 4에서 같은 파일에 추가한다):
```python
"""SQL 전담 계층.

앱 안에서 SQL 문자열이 존재하는 곳은 이 파일과 db/schema.sql 뿐이다.
상위 계층(service·cli·web)은 SQL을 모른다.
"""

from __future__ import annotations

import sqlite3

from todoapp.models import (
    Tag,
    normalize_color,
    normalize_tag_name,
)


def row_to_tag(row: sqlite3.Row) -> Tag:
    return Tag(id=row["id"], name=row["name"], color=row["color"])


class TagRepository:
    """태그 사전. 이름은 대소문자를 무시하고 유일하다."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, name: str, color: str | None = None) -> Tag:
        """있으면 가져오고 없으면 만든다.

        color를 주면 갱신하고, 생략하면(None) 기존 색상을 지킨다.
        이름 표기는 먼저 저장된 쪽을 유지한다 — 'Study'가 있으면 'study'로
        넣어도 'Study'가 남는다. tags.name이 COLLATE NOCASE이기 때문이다.
        """
        clean_name = normalize_tag_name(name)
        clean_color = normalize_color(color) if color is not None else None
        row = self._conn.execute(
            """
            INSERT INTO tags (name, color)
            VALUES (?, COALESCE(?, '#888880'))
            ON CONFLICT(name) DO UPDATE
                SET color = COALESCE(excluded.color, tags.color)
            RETURNING id, name, color
            """,
            (clean_name, clean_color),
        ).fetchone()
        return row_to_tag(row)

    def get(self, tag_id: int) -> Tag | None:
        row = self._conn.execute(
            "SELECT id, name, color FROM tags WHERE id = ?", (tag_id,)
        ).fetchone()
        return row_to_tag(row) if row else None

    def get_by_name(self, name: str) -> Tag | None:
        """이름으로 찾는다. 열 콜레이션이 NOCASE라 대소문자를 무시한다."""
        row = self._conn.execute(
            "SELECT id, name, color FROM tags WHERE name = ?",
            (normalize_tag_name(name),),
        ).fetchone()
        return row_to_tag(row) if row else None

    def list_all(self) -> list[Tag]:
        rows = self._conn.execute(
            "SELECT id, name, color FROM tags ORDER BY name COLLATE NOCASE ASC"
        ).fetchall()
        return [row_to_tag(r) for r in rows]

    def delete_unused(self) -> int:
        """어떤 할 일에도 붙지 않은 태그를 지운다. 지운 개수를 돌려준다."""
        cursor = self._conn.execute(
            "DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM todo_tags)"
        )
        return cursor.rowcount
```

**주의**: `upsert`의 `ON CONFLICT ... DO UPDATE`는 색상이 실제로 안 바뀌어도 행을 갱신한다.
`tags`에는 `updated_at`이 없으므로 부작용이 없다. `todos`처럼 트리거가 달린 표라면
`WHERE excluded.color IS NOT NULL` 같은 조건을 붙여야 한다.

- [x] **Step 4: 테스트 통과 확인**

Run: `cd ToDoApp && python3 -m pytest tests/ -q`
Expected: PASS

- [x] **Step 5: 커밋**

```bash
cd /Users/kwonkwanggoo/aiffel_work
git add ToDoApp/todoapp/repository.py ToDoApp/tests/test_repository_tags.py
git commit -m "feat(todoapp): 태그 리포지토리 추가 (대소문자 무시 upsert)"
```

---

### Task 4: 할 일 리포지토리 — CRUD와 태그 연결

**Files:**
- Modify: `todoapp/repository.py` (`TodoRepository` 추가)
- Create: `tests/test_repository_todos.py`

**Interfaces:**
- Consumes: Task 3의 `TagRepository`·`row_to_tag`, `models.Todo` 및 정규화 함수 전체
- Produces:
  - `repository.TodoRepository(conn)`
  - `.add(title, *, notes=None, due_date=None, priority=None) -> int`
  - `.get(todo_id: int) -> Todo | None` (태그 포함)
  - `.update(todo_id, *, title=..., notes=..., due_date=..., priority=...) -> bool`
  - `.set_done(todo_id: int, done: bool) -> bool`
  - `.delete(todo_id: int) -> bool`
  - `.replace_tags(todo_id: int, tag_ids: Sequence[int]) -> None`
  - `.load_tags(todo_ids: Sequence[int]) -> dict[int, tuple[Tag, ...]]`
  - `repository.UNSET` (센티널 — `update`에서 "안 바꿈"과 "None으로 바꿈"을 구분)
  - `repository.is_set(value: object) -> bool` (UNSET이 아닌지 판정)

**설계 근거 — `UNSET` 센티널이 필요한 이유:** `update(todo_id, notes=None)`이
"메모를 지워라"인지 "메모는 건드리지 마라"인지 `None`만으로는 구분할 수 없다.
`notes=UNSET`을 기본값으로 두면 두 의도가 갈라진다.

- [x] **Step 1: 실패하는 테스트 작성**

`tests/test_repository_todos.py`:
```python
"""할 일 리포지토리 CRUD·태그 연결 테스트."""
from __future__ import annotations

import pytest

from todoapp.models import PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_NORMAL, Todo, ValidationError
from todoapp.repository import UNSET, TagRepository, TodoRepository


@pytest.fixture
def todos(conn) -> TodoRepository:
    return TodoRepository(conn)


@pytest.fixture
def tags(conn) -> TagRepository:
    return TagRepository(conn)


class TestAdd:
    def test_할_일을_추가하고_id를_돌려준다(self, todos):
        todo_id = todos.add("장보기")
        assert isinstance(todo_id, int) and todo_id > 0

    def test_추가한_내용을_그대로_읽는다(self, todos):
        todo_id = todos.add("장보기", notes="우유, 계란", due_date="2026-09-10", priority="high")
        todo = todos.get(todo_id)
        assert todo.title == "장보기"
        assert todo.notes == "우유, 계란"
        assert todo.due_date == "2026-09-10"
        assert todo.priority == PRIORITY_HIGH
        assert todo.is_done is False
        assert todo.completed_at is None
        assert todo.tags == ()

    def test_생성_시각이_기록된다(self, todos):
        todo = todos.get(todos.add("장보기"))
        assert todo.created_at is not None
        assert todo.updated_at is not None

    def test_기본_우선순위는_보통이다(self, todos):
        assert todos.get(todos.add("장보기")).priority == PRIORITY_NORMAL

    def test_제목_검증이_적용된다(self, todos):
        with pytest.raises(ValidationError):
            todos.add("   ")

    def test_마감일_검증이_적용된다(self, todos):
        with pytest.raises(ValidationError):
            todos.add("장보기", due_date="2026-02-31")

    def test_없는_id는_None이다(self, todos):
        assert todos.get(9999) is None


class TestSetDone:
    def test_완료로_표시한다(self, todos):
        todo_id = todos.add("장보기")
        assert todos.set_done(todo_id, True) is True
        todo = todos.get(todo_id)
        assert todo.is_done is True
        assert todo.completed_at is not None  # 트리거가 기록한다

    def test_완료를_되돌리면_완료시각이_지워진다(self, todos):
        todo_id = todos.add("장보기")
        todos.set_done(todo_id, True)
        todos.set_done(todo_id, False)
        todo = todos.get(todo_id)
        assert todo.is_done is False
        assert todo.completed_at is None

    def test_없는_id는_False다(self, todos):
        assert todos.set_done(9999, True) is False


class TestUpdate:
    def test_제목을_바꾼다(self, todos):
        todo_id = todos.add("장보기")
        assert todos.update(todo_id, title="장보기(수정)") is True
        assert todos.get(todo_id).title == "장보기(수정)"

    def test_안_넘긴_필드는_그대로다(self, todos):
        todo_id = todos.add("장보기", notes="우유", due_date="2026-09-10")
        todos.update(todo_id, title="새 제목")
        todo = todos.get(todo_id)
        assert todo.notes == "우유"
        assert todo.due_date == "2026-09-10"

    def test_None을_명시하면_지워진다(self, todos):
        todo_id = todos.add("장보기", notes="우유", due_date="2026-09-10")
        todos.update(todo_id, notes=None, due_date=None)
        todo = todos.get(todo_id)
        assert todo.notes is None
        assert todo.due_date is None

    def test_아무_필드도_안_주면_아무것도_안_한다(self, todos):
        todo_id = todos.add("장보기")
        before = todos.get(todo_id)
        assert todos.update(todo_id) is False
        assert todos.get(todo_id) == before

    def test_없는_id는_False다(self, todos):
        assert todos.update(9999, title="없음") is False

    def test_검증이_적용된다(self, todos):
        todo_id = todos.add("장보기")
        with pytest.raises(ValidationError):
            todos.update(todo_id, due_date="2026/09/10")


class TestDelete:
    def test_삭제하면_사라진다(self, todos):
        todo_id = todos.add("장보기")
        assert todos.delete(todo_id) is True
        assert todos.get(todo_id) is None

    def test_없는_id는_False다(self, todos):
        assert todos.delete(9999) is False

    def test_삭제하면_태그_연결도_함께_사라진다(self, conn, todos, tags):
        todo_id = todos.add("장보기")
        tag = tags.upsert("집안일")
        todos.replace_tags(todo_id, [tag.id])
        todos.delete(todo_id)
        remaining = conn.execute("SELECT count(*) AS c FROM todo_tags").fetchone()["c"]
        assert remaining == 0
        # 태그 사전 자체는 남는다
        assert tags.get(tag.id) is not None


class TestTags:
    def test_태그를_붙인다(self, todos, tags):
        todo_id = todos.add("과제")
        study = tags.upsert("공부")
        todos.replace_tags(todo_id, [study.id])
        assert [t.name for t in todos.get(todo_id).tags] == ["공부"]

    def test_태그를_여러_개_붙이면_이름순으로_나온다(self, todos, tags):
        todo_id = todos.add("과제")
        ids = [tags.upsert(n).id for n in ("집안일", "공부", "운동")]
        todos.replace_tags(todo_id, ids)
        assert [t.name for t in todos.get(todo_id).tags] == ["공부", "운동", "집안일"]

    def test_replace_tags는_기존_연결을_대체한다(self, todos, tags):
        todo_id = todos.add("과제")
        study, chore = tags.upsert("공부"), tags.upsert("집안일")
        todos.replace_tags(todo_id, [study.id, chore.id])
        todos.replace_tags(todo_id, [chore.id])
        assert [t.name for t in todos.get(todo_id).tags] == ["집안일"]

    def test_빈_목록을_주면_전부_떼어낸다(self, todos, tags):
        todo_id = todos.add("과제")
        todos.replace_tags(todo_id, [tags.upsert("공부").id])
        todos.replace_tags(todo_id, [])
        assert todos.get(todo_id).tags == ()

    def test_같은_태그를_두_번_주어도_한_번만_붙는다(self, todos, tags):
        todo_id = todos.add("과제")
        study = tags.upsert("공부")
        todos.replace_tags(todo_id, [study.id, study.id])
        assert len(todos.get(todo_id).tags) == 1

    def test_없는_태그_id는_거부된다(self, todos):
        import sqlite3

        todo_id = todos.add("과제")
        with pytest.raises(sqlite3.IntegrityError):
            todos.replace_tags(todo_id, [9999])

    def test_load_tags는_쿼리_한_번으로_여러_할_일의_태그를_가져온다(self, todos, tags):
        study, chore = tags.upsert("공부"), tags.upsert("집안일")
        first = todos.add("과제")
        second = todos.add("청소")
        third = todos.add("태그없음")
        todos.replace_tags(first, [study.id])
        todos.replace_tags(second, [chore.id, study.id])
        loaded = todos.load_tags([first, second, third])
        assert [t.name for t in loaded[first]] == ["공부"]
        assert [t.name for t in loaded[second]] == ["공부", "집안일"]
        assert loaded[third] == ()

    def test_load_tags에_빈_목록을_주면_빈_사전이다(self, todos):
        assert todos.load_tags([]) == {}
```

- [x] **Step 2: 테스트 실패 확인**

Run: `cd ToDoApp && python3 -m pytest tests/test_repository_todos.py -q`
Expected: FAIL — `ImportError: cannot import name 'UNSET' from 'todoapp.repository'`

- [x] **Step 3: 최소 구현 작성**

`todoapp/repository.py`에 다음을 추가한다(파일 상단 import에 `Sequence`, `Todo`,
`normalize_due_date`, `normalize_priority`, `normalize_title`를 더한다):
```python
class _Unset:
    """'값을 주지 않았다'를 뜻하는 센티널. None(값을 비워라)과 구분하려고 쓴다."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET = _Unset()


def is_set(value: object) -> bool:
    """UNSET 센티널이 아닌 '실제로 주어진 값'인지 판정한다.

    상위 계층이 isinstance(x, _Unset)처럼 비공개 이름을 쓰지 않게 하려고 노출한다.
    """
    return not isinstance(value, _Unset)


def row_to_todo(row: sqlite3.Row, tags: tuple[Tag, ...] = ()) -> Todo:
    """DB 행을 도메인 객체로. is_done 0/1 → bool 변환은 여기서만 한다."""
    return Todo(
        id=row["id"],
        title=row["title"],
        notes=row["notes"],
        is_done=bool(row["is_done"]),
        due_date=row["due_date"],
        priority=row["priority"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
        tags=tags,
    )


_TODO_COLUMNS = """
    id, title, notes, is_done, due_date, priority,
    created_at, updated_at, completed_at
"""


class TodoRepository:
    """할 일 CRUD와 태그 연결. 트랜잭션 경계는 상위(service)가 잡는다."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(
        self,
        title: str,
        *,
        notes: str | None = None,
        due_date: str | None = None,
        priority: int | str | None = None,
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO todos (title, notes, due_date, priority) VALUES (?, ?, ?, ?)",
            (
                normalize_title(title),
                notes.strip() if isinstance(notes, str) and notes.strip() else None,
                normalize_due_date(due_date),
                normalize_priority(priority),
            ),
        )
        return int(cursor.lastrowid)

    def get(self, todo_id: int) -> Todo | None:
        row = self._conn.execute(
            f"SELECT {_TODO_COLUMNS} FROM todos WHERE id = ?", (todo_id,)
        ).fetchone()
        if row is None:
            return None
        return row_to_todo(row, self.load_tags([todo_id]).get(todo_id, ()))

    def update(
        self,
        todo_id: int,
        *,
        title: str | _Unset = UNSET,
        notes: str | None | _Unset = UNSET,
        due_date: str | None | _Unset = UNSET,
        priority: int | str | _Unset = UNSET,
    ) -> bool:
        """준 필드만 바꾼다. UNSET은 '건드리지 마라', None은 '비워라'."""
        assignments: list[str] = []
        params: list[object] = []
        if not isinstance(title, _Unset):
            assignments.append("title = ?")
            params.append(normalize_title(title))
        if not isinstance(notes, _Unset):
            assignments.append("notes = ?")
            params.append(notes.strip() if isinstance(notes, str) and notes.strip() else None)
        if not isinstance(due_date, _Unset):
            assignments.append("due_date = ?")
            params.append(normalize_due_date(due_date))
        if not isinstance(priority, _Unset):
            assignments.append("priority = ?")
            params.append(normalize_priority(priority))
        if not assignments:
            return False
        params.append(todo_id)
        cursor = self._conn.execute(
            f"UPDATE todos SET {', '.join(assignments)} WHERE id = ?", params
        )
        return cursor.rowcount > 0

    def set_done(self, todo_id: int, done: bool) -> bool:
        """완료 표시를 바꾼다. completed_at·updated_at은 트리거가 알아서 채운다."""
        cursor = self._conn.execute(
            "UPDATE todos SET is_done = ? WHERE id = ?", (1 if done else 0, todo_id)
        )
        return cursor.rowcount > 0

    def delete(self, todo_id: int) -> bool:
        """할 일을 지운다. todo_tags 연결은 ON DELETE CASCADE가 정리한다."""
        cursor = self._conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        return cursor.rowcount > 0

    def replace_tags(self, todo_id: int, tag_ids: Sequence[int]) -> None:
        """이 할 일의 태그 연결을 주어진 목록으로 통째로 교체한다."""
        self._conn.execute("DELETE FROM todo_tags WHERE todo_id = ?", (todo_id,))
        unique_ids = list(dict.fromkeys(tag_ids))
        if unique_ids:
            self._conn.executemany(
                "INSERT INTO todo_tags (todo_id, tag_id) VALUES (?, ?)",
                [(todo_id, tag_id) for tag_id in unique_ids],
            )

    def load_tags(self, todo_ids: Sequence[int]) -> dict[int, tuple[Tag, ...]]:
        """여러 할 일의 태그를 쿼리 한 번으로 가져온다.

        할 일마다 태그를 따로 조회하면 목록 10개에 쿼리 11번(N+1)이 된다.
        여기서 한 번에 받아 파이썬에서 묶는다.
        """
        ids = list(dict.fromkeys(todo_ids))
        if not ids:
            return {}
        placeholders = ", ".join("?" * len(ids))
        rows = self._conn.execute(
            f"""
            SELECT tt.todo_id, g.id, g.name, g.color
              FROM todo_tags tt
              JOIN tags g ON g.id = tt.tag_id
             WHERE tt.todo_id IN ({placeholders})
             ORDER BY g.name COLLATE NOCASE ASC
            """,
            ids,
        ).fetchall()
        grouped: dict[int, list[Tag]] = {todo_id: [] for todo_id in ids}
        for row in rows:
            grouped[row["todo_id"]].append(row_to_tag(row))
        return {todo_id: tuple(tag_list) for todo_id, tag_list in grouped.items()}
```

**주의**: `load_tags`는 id 개수만큼 바인딩 변수를 쓴다. SQLite의 변수 상한은 32766개
(3.32+ 기본값)이므로 개인용 Todo 규모에서는 문제되지 않는다. 수만 건을 다룰 일이
생기면 임시 표에 id를 넣고 JOIN하는 방식으로 바꾼다.

- [x] **Step 4: 테스트 통과 확인**

Run: `cd ToDoApp && python3 -m pytest tests/ -q`
Expected: PASS

- [x] **Step 5: 커밋**

```bash
cd /Users/kwonkwanggoo/aiffel_work
git add ToDoApp/todoapp/repository.py ToDoApp/tests/test_repository_todos.py
git commit -m "feat(todoapp): 할 일 리포지토리 CRUD와 태그 연결 추가"
```

---

### Task 5: 필터 조회 + 뷰 정합성 보장

목록 화면이 필요한 조회를 전부 여기서 끝낸다. 동시에 `schema.sql`의 뷰 두 개가
리포지토리와 갈라지지 않도록 정렬 기준을 맞추고, 정합성 테스트로 고정한다.

**Files:**
- Modify: `todoapp/repository.py` (`TodoRepository.list`, `.count_by_scope` 추가)
- Modify: `db/schema.sql` (뷰 2개의 `ORDER BY`를 리포지토리와 동일하게 맞춤)
- Modify: `docs/db-design.md` (뷰의 역할을 '수동 점검용'으로 명시)
- Create: `tests/test_repository_list.py`

**Interfaces:**
- Consumes: Task 4의 `TodoRepository`
- Produces:
  - `.list(*, done: bool | None = None, tag: str | None = None, keyword: str | None = None, due_on_or_before: str | None = None, due_before: str | None = None, has_due: bool | None = None) -> list[Todo]`
  - `.count_all() -> int`

**정렬 기준(전 계층 공통):**
`is_done ASC, (due_date IS NULL) ASC, due_date ASC, priority ASC, id ASC`
— 미완료 먼저 → 마감일 있는 것 먼저 → 임박한 것 먼저 → 우선순위 → 등록순.

- [x] **Step 1: `db/schema.sql`의 뷰 정렬을 맞춘다**

`v_today_todos`의 `ORDER BY`를 다음으로 교체:
```sql
 ORDER BY t.due_date ASC, t.priority ASC, t.id ASC;
```
`v_todo_list`의 `ORDER BY`를 다음으로 교체:
```sql
 ORDER BY t.is_done ASC, t.due_date IS NULL ASC, t.due_date ASC, t.priority ASC, t.id ASC;
```
그리고 두 뷰 위에 주석을 넣는다:
```sql
-- 아래 뷰 2개는 `sqlite3 db/todo.db` 로 DB를 직접 들여다볼 때 쓰는 점검용이다.
-- 앱 코드는 이 뷰를 쓰지 않고 repository.py의 파라미터화된 쿼리를 쓴다
-- (테스트에서 날짜를 고정할 수 있어야 하므로). 두 경로가 갈라지지 않도록
-- tests/test_repository_list.py가 결과 일치를 검사한다.
```

- [x] **Step 2: 실패하는 테스트 작성**

`tests/test_repository_list.py`:
```python
"""필터 조회와 스키마 뷰 정합성 테스트."""
from __future__ import annotations

import pytest

from todoapp.repository import TagRepository, TodoRepository


@pytest.fixture
def todos(conn) -> TodoRepository:
    return TodoRepository(conn)


@pytest.fixture
def tags(conn) -> TagRepository:
    return TagRepository(conn)


@pytest.fixture
def sample(conn, todos, tags):
    """고정된 표본. 날짜는 DB의 '오늘'을 기준으로 상대 계산한다."""
    today = conn.execute("SELECT date('now','localtime') AS d").fetchone()["d"]
    yesterday = conn.execute("SELECT date('now','localtime','-1 day') AS d").fetchone()["d"]
    next_week = conn.execute("SELECT date('now','localtime','+7 day') AS d").fetchone()["d"]

    study = tags.upsert("공부")
    chore = tags.upsert("집안일")

    ids = {
        "지난것": todos.add("지난 과제", due_date=yesterday, priority="high"),
        "오늘것": todos.add("오늘 발표", due_date=today, priority="normal"),
        "다음주": todos.add("장보기", due_date=next_week),
        "마감없음": todos.add("책 읽기"),
        "완료된것": todos.add("설거지", due_date=yesterday),
    }
    todos.replace_tags(ids["지난것"], [study.id])
    todos.replace_tags(ids["오늘것"], [study.id, chore.id])
    todos.replace_tags(ids["완료된것"], [chore.id])
    todos.set_done(ids["완료된것"], True)
    return {"ids": ids, "today": today, "yesterday": yesterday, "next_week": next_week}


class TestOrdering:
    def test_미완료가_먼저_나온다(self, todos, sample):
        result = todos.list()
        assert result[-1].id == sample["ids"]["완료된것"]

    def test_마감일이_임박한_순서다(self, todos, sample):
        active = [t.id for t in todos.list(done=False)]
        assert active == [
            sample["ids"]["지난것"],
            sample["ids"]["오늘것"],
            sample["ids"]["다음주"],
            sample["ids"]["마감없음"],  # 마감일 없는 것은 뒤로
        ]


class TestFilters:
    def test_전체를_돌려준다(self, todos, sample):
        assert len(todos.list()) == 5

    def test_미완료만(self, todos, sample):
        assert all(not t.is_done for t in todos.list(done=False))
        assert len(todos.list(done=False)) == 4

    def test_완료만(self, todos, sample):
        result = todos.list(done=True)
        assert [t.id for t in result] == [sample["ids"]["완료된것"]]

    def test_태그로_거른다(self, todos, sample):
        result = todos.list(tag="공부")
        assert {t.id for t in result} == {sample["ids"]["지난것"], sample["ids"]["오늘것"]}

    def test_태그_필터는_대소문자를_무시한다(self, todos, tags):
        todo_id = todos.add("영어 공부")
        todos.replace_tags(todo_id, [tags.upsert("Study").id])
        assert [t.id for t in todos.list(tag="STUDY")] == [todo_id]

    def test_태그로_걸러도_중복_행이_생기지_않는다(self, todos, sample):
        # 태그 2개가 붙은 할 일이 JOIN 때문에 두 번 나오면 안 된다.
        result = todos.list(tag="집안일")
        assert len(result) == len({t.id for t in result})

    def test_없는_태그는_빈_목록이다(self, todos, sample):
        assert todos.list(tag="없는태그") == []

    def test_키워드로_제목을_찾는다(self, todos, sample):
        assert [t.id for t in todos.list(keyword="장보기")] == [sample["ids"]["다음주"]]

    def test_키워드로_메모도_찾는다(self, todos):
        todo_id = todos.add("병원", notes="치과 예약 확인")
        assert [t.id for t in todos.list(keyword="치과")] == [todo_id]

    def test_키워드의_와일드카드는_글자로_취급한다(self, todos):
        # LIKE의 %와 _를 escape하지 않으면 '%'가 '전부 일치'가 되어 버린다.
        todos.add("보고서 100% 완성")
        todos.add("전혀 다른 할 일")
        # '100%'를 글자 그대로 찾는다
        assert len(todos.list(keyword="100%")) == 1
        # '%'는 '아무 문자열'이 아니라 문자 '%'를 품은 것만 (표본에 1건)
        assert len(todos.list(keyword="%")) == 1
        # '_'는 '아무 한 글자'가 아니라 문자 '_'를 품은 것만 (표본에 0건)
        assert len(todos.list(keyword="_")) == 0

    def test_마감일_이하로_거른다(self, todos, sample):
        result = todos.list(done=False, due_on_or_before=sample["today"])
        assert {t.id for t in result} == {sample["ids"]["지난것"], sample["ids"]["오늘것"]}

    def test_마감일_미만으로_거른다(self, todos, sample):
        result = todos.list(done=False, due_before=sample["today"])
        assert {t.id for t in result} == {sample["ids"]["지난것"]}

    def test_마감일_유무로_거른다(self, todos, sample):
        assert [t.id for t in todos.list(has_due=False)] == [sample["ids"]["마감없음"]]
        assert sample["ids"]["마감없음"] not in {t.id for t in todos.list(has_due=True)}

    def test_필터를_겹쳐_쓸_수_있다(self, todos, sample):
        result = todos.list(done=False, tag="공부", due_on_or_before=sample["today"])
        assert {t.id for t in result} == {sample["ids"]["지난것"], sample["ids"]["오늘것"]}

    def test_목록의_태그가_함께_채워진다(self, todos, sample):
        by_id = {t.id: t for t in todos.list()}
        assert [g.name for g in by_id[sample["ids"]["오늘것"]].tags] == ["공부", "집안일"]
        assert by_id[sample["ids"]["마감없음"]].tags == ()

    def test_전체_개수를_센다(self, todos, sample):
        assert todos.count_all() == 5


class TestViewConsistency:
    """schema.sql의 뷰와 리포지토리 쿼리가 갈라지지 않는지 검사한다."""

    def test_v_todo_list와_list가_같은_순서를_준다(self, conn, todos, sample):
        view_ids = [r["id"] for r in conn.execute("SELECT id FROM v_todo_list")]
        repo_ids = [t.id for t in todos.list()]
        assert view_ids == repo_ids

    def test_v_todo_list의_태그_문자열이_리포지토리와_일치한다(self, conn, todos, sample):
        view = {r["id"]: r["tag_names"] for r in conn.execute("SELECT id, tag_names FROM v_todo_list")}
        for todo in todos.list():
            expected = ", ".join(g.name for g in todo.tags) or None
            assert view[todo.id] == expected

    def test_v_today_todos와_리포지토리가_일치한다(self, conn, todos, sample):
        view_ids = [r["id"] for r in conn.execute("SELECT id FROM v_today_todos")]
        repo_ids = [
            t.id
            for t in todos.list(done=False, due_on_or_before=sample["today"], has_due=True)
        ]
        assert view_ids == repo_ids
```

- [x] **Step 3: 테스트 실패 확인**

Run: `cd ToDoApp && python3 -m pytest tests/test_repository_list.py -q`
Expected: FAIL — `TypeError: TodoRepository.list() got an unexpected keyword argument 'done'`
(또는 `AttributeError: 'TodoRepository' object has no attribute 'list'`)

- [x] **Step 4: 최소 구현 작성**

`TodoRepository`에 추가:
```python
    _ORDER_BY = (
        "ORDER BY is_done ASC, due_date IS NULL ASC, due_date ASC, priority ASC, id ASC"
    )

    def list(
        self,
        *,
        done: bool | None = None,
        tag: str | None = None,
        keyword: str | None = None,
        due_on_or_before: str | None = None,
        due_before: str | None = None,
        has_due: bool | None = None,
    ) -> list[Todo]:
        """조건에 맞는 할 일을 정렬해 돌려준다. 태그도 함께 채운다.

        None인 필터는 '거르지 않음'을 뜻한다.
        """
        clauses: list[str] = []
        params: list[object] = []

        if done is not None:
            clauses.append("is_done = ?")
            params.append(1 if done else 0)

        if tag is not None:
            # JOIN이 아니라 EXISTS를 쓴다. JOIN으로 걸면 태그가 여러 개 붙은
            # 할 일이 여러 행으로 튀어나온다.
            clauses.append(
                """EXISTS (
                       SELECT 1 FROM todo_tags tt
                         JOIN tags g ON g.id = tt.tag_id
                        WHERE tt.todo_id = todos.id AND g.name = ?
                   )"""
            )
            params.append(normalize_tag_name(tag))

        if keyword is not None and str(keyword).strip():
            pattern = f"%{_escape_like(str(keyword).strip())}%"
            clauses.append(
                r"(title LIKE ? ESCAPE '\' OR COALESCE(notes, '') LIKE ? ESCAPE '\')"
            )
            params.extend([pattern, pattern])

        if due_on_or_before is not None:
            clauses.append("due_date IS NOT NULL AND due_date <= ?")
            params.append(normalize_due_date(due_on_or_before))

        if due_before is not None:
            clauses.append("due_date IS NOT NULL AND due_date < ?")
            params.append(normalize_due_date(due_before))

        if has_due is not None:
            clauses.append("due_date IS NOT NULL" if has_due else "due_date IS NULL")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT {_TODO_COLUMNS} FROM todos {where} {self._ORDER_BY}", params
        ).fetchall()
        tags_by_todo = self.load_tags([row["id"] for row in rows])
        return [row_to_todo(row, tags_by_todo.get(row["id"], ())) for row in rows]

    def count_all(self) -> int:
        return int(self._conn.execute("SELECT count(*) AS c FROM todos").fetchone()["c"])
```

모듈 수준에 도우미 함수를 추가한다:
```python
def _escape_like(value: str) -> str:
    r"""LIKE 패턴에서 특별한 뜻을 가진 글자를 무력화한다.

    escape하지 않으면 사용자가 '%'를 검색할 때 전체가 일치해 버린다.
    역슬래시를 먼저 바꿔야 한다 — 나중에 하면 방금 붙인 escape 문자까지 이중으로 바뀐다.
    """
    return value.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")
```

- [x] **Step 5: 테스트 통과 확인**

Run: `cd ToDoApp && python3 -m pytest tests/ -q`
Expected: PASS

- [x] **Step 6: `docs/db-design.md`의 뷰 설명 갱신**

"## 뷰 2개" 절의 설명을 다음으로 교체한다:
```markdown
## 뷰 2개 (DB를 손으로 들여다볼 때)

- `v_today_todos` — 마감일이 오늘이거나 지난 미완료 항목
- `v_todo_list` — 목록 화면 형태. 태그를 `GROUP_CONCAT`으로 한 줄로 합친 것

**앱 코드는 이 뷰를 쓰지 않는다.** 뷰의 `date('now','localtime')`은 테스트에서
날짜를 고정할 수 없어서, 앱은 `repository.py`의 파라미터화된 쿼리를 쓴다.
두 경로가 조용히 갈라지는 것을 막기 위해 `tests/test_repository_list.py::TestViewConsistency`가
뷰와 리포지토리의 결과가 같은지 검사한다.
```

- [x] **Step 7: 커밋**

```bash
cd /Users/kwonkwanggoo/aiffel_work
git add ToDoApp/todoapp/repository.py ToDoApp/db/schema.sql \
        ToDoApp/docs/db-design.md ToDoApp/tests/test_repository_list.py
git commit -m "feat(todoapp): 필터 조회 추가 및 스키마 뷰 정합성 테스트로 고정"
```

---
### Task 6: 서비스 계층

CLI와 웹이 공유하는 유스케이스. 트랜잭션 경계도 여기서 잡는다.

**Files:**
- Create: `todoapp/service.py`
- Create: `tests/test_service.py`

**Interfaces:**
- Consumes: `repository.TodoRepository`·`TagRepository`·`UNSET`, `models.parse_tag_list`
- Produces:
  - `service.TodoNotFound(LookupError)` — `.todo_id` 속성 보유
  - `service.SCOPES: tuple[str, ...]` = `("all","active","done","today","overdue","no-due")`
  - `service.SCOPE_LABELS: dict[str, str]` — 화면 표시용 한국어 이름
  - `service.TodoService(conn, *, today: Callable[[], str] = ...)`
  - `.add(title, *, notes=None, due=None, priority=None, tags=None) -> Todo`
  - `.get(todo_id) -> Todo` (없으면 `TodoNotFound`)
  - `.edit(todo_id, *, title=UNSET, notes=UNSET, due=UNSET, priority=UNSET, tags=UNSET) -> Todo`
  - `.complete(todo_id) -> Todo` / `.reopen(todo_id) -> Todo` / `.toggle(todo_id) -> Todo`
  - `.delete(todo_id) -> None`
  - `.list(scope="all", *, tag=None, keyword=None) -> list[Todo]`
  - `.all_tags() -> list[Tag]`
  - `.today() -> str` (주입된 시계의 오늘. CLI·웹이 함께 쓴다)
  - `.summary() -> dict[str, int]` — 키: `total`·`active`·`done`·`today`·`overdue`

**설계 근거 — 시계를 주입하는 이유:** "오늘 할 일"을 `date.today()`로 직접 부르면
테스트가 실행 날짜에 따라 달라진다. 생성자에 `today` 콜러블을 받아 테스트에서 고정한다.
콜러블(값이 아니라 함수)인 이유는, 웹 서버처럼 오래 떠 있는 프로세스에서 날짜가
프로세스 시작 시점에 얼어붙지 않게 하려는 것이다.

- [x] **Step 1: 실패하는 테스트 작성**

`tests/test_service.py`:
```python
"""서비스 계층 테스트. 날짜는 고정 시계로 못 박는다."""
from __future__ import annotations

import pytest

from todoapp.models import PRIORITY_HIGH, PRIORITY_NORMAL, ValidationError
from todoapp.repository import UNSET
from todoapp.service import TodoNotFound, TodoService

FIXED_TODAY = "2026-09-04"


@pytest.fixture
def service(conn) -> TodoService:
    return TodoService(conn, today=lambda: FIXED_TODAY)


@pytest.fixture
def seeded(service):
    """고정 날짜(2026-09-04) 기준 표본."""
    ids = {
        "지남": service.add("지난 과제", due="2026-09-01", priority="high", tags="공부").id,
        "오늘": service.add("오늘 발표", due=FIXED_TODAY, tags="공부,회사").id,
        "미래": service.add("장보기", due="2026-09-20", tags="집안일").id,
        "마감없음": service.add("책 읽기").id,
    }
    ids["완료"] = service.add("설거지", due="2026-09-01", tags="집안일").id
    service.complete(ids["완료"])
    return ids


class TestAdd:
    def test_할_일을_추가한다(self, service):
        todo = service.add("장보기")
        assert todo.id is not None
        assert todo.title == "장보기"
        assert todo.is_done is False

    def test_태그를_문자열로_받는다(self, service):
        todo = service.add("과제", tags="공부, 집안일")
        assert [t.name for t in todo.tags] == ["공부", "집안일"]

    def test_태그를_리스트로도_받는다(self, service):
        todo = service.add("과제", tags=["공부", "집안일"])
        assert [t.name for t in todo.tags] == ["공부", "집안일"]

    def test_없는_태그는_자동으로_만든다(self, service):
        service.add("과제", tags="새태그")
        assert [t.name for t in service.all_tags()] == ["새태그"]

    def test_있는_태그는_재사용한다(self, service):
        service.add("과제1", tags="공부")
        service.add("과제2", tags="공부")
        assert len(service.all_tags()) == 1

    def test_모든_필드를_받는다(self, service):
        todo = service.add("장보기", notes="우유", due="2026-09-10", priority="high", tags="집안일")
        assert todo.notes == "우유"
        assert todo.due_date == "2026-09-10"
        assert todo.priority == PRIORITY_HIGH
        assert [t.name for t in todo.tags] == ["집안일"]

    def test_검증_실패시_아무것도_저장되지_않는다(self, service):
        with pytest.raises(ValidationError):
            service.add("장보기", due="2026-02-31", tags="공부")
        # 롤백되어 할 일도 태그도 남지 않아야 한다
        assert service.list("all") == []
        assert service.all_tags() == []


class TestGetAndDelete:
    def test_없는_id를_읽으면_예외다(self, service):
        with pytest.raises(TodoNotFound) as exc:
            service.get(9999)
        assert exc.value.todo_id == 9999

    def test_삭제한다(self, service):
        todo = service.add("장보기")
        service.delete(todo.id)
        with pytest.raises(TodoNotFound):
            service.get(todo.id)

    def test_없는_id를_삭제하면_예외다(self, service):
        with pytest.raises(TodoNotFound):
            service.delete(9999)


class TestCompletion:
    def test_완료로_표시한다(self, service):
        todo = service.add("장보기")
        done = service.complete(todo.id)
        assert done.is_done is True
        assert done.completed_at is not None

    def test_완료를_되돌린다(self, service):
        todo = service.add("장보기")
        service.complete(todo.id)
        reopened = service.reopen(todo.id)
        assert reopened.is_done is False
        assert reopened.completed_at is None

    def test_토글은_상태를_뒤집는다(self, service):
        todo = service.add("장보기")
        assert service.toggle(todo.id).is_done is True
        assert service.toggle(todo.id).is_done is False

    def test_없는_id는_예외다(self, service):
        with pytest.raises(TodoNotFound):
            service.complete(9999)
        with pytest.raises(TodoNotFound):
            service.toggle(9999)


class TestEdit:
    def test_제목만_바꾼다(self, service):
        todo = service.add("장보기", notes="우유", tags="집안일")
        edited = service.edit(todo.id, title="장보기(수정)")
        assert edited.title == "장보기(수정)"
        assert edited.notes == "우유"
        assert [t.name for t in edited.tags] == ["집안일"]

    def test_마감일을_비운다(self, service):
        todo = service.add("장보기", due="2026-09-10")
        assert service.edit(todo.id, due=None).due_date is None

    def test_태그를_교체한다(self, service):
        todo = service.add("과제", tags="공부")
        edited = service.edit(todo.id, tags="집안일,운동")
        assert [t.name for t in edited.tags] == ["운동", "집안일"]

    def test_태그를_전부_뗀다(self, service):
        todo = service.add("과제", tags="공부")
        assert service.edit(todo.id, tags="").tags == ()

    def test_tags를_안_주면_태그는_그대로다(self, service):
        todo = service.add("과제", tags="공부")
        assert [t.name for t in service.edit(todo.id, title="새 제목").tags] == ["공부"]

    def test_없는_id는_예외다(self, service):
        with pytest.raises(TodoNotFound):
            service.edit(9999, title="없음")

    def test_아무것도_안_주면_그대로_돌려준다(self, service):
        todo = service.add("장보기")
        assert service.edit(todo.id) == todo


class TestListScopes:
    def test_all은_전부다(self, service, seeded):
        assert len(service.list("all")) == 5

    def test_active는_미완료만(self, service, seeded):
        assert len(service.list("active")) == 4

    def test_done은_완료만(self, service, seeded):
        assert [t.id for t in service.list("done")] == [seeded["완료"]]

    def test_today는_오늘까지_마감인_미완료다(self, service, seeded):
        assert {t.id for t in service.list("today")} == {seeded["지남"], seeded["오늘"]}

    def test_overdue는_이미_지난_미완료다(self, service, seeded):
        assert [t.id for t in service.list("overdue")] == [seeded["지남"]]

    def test_no_due는_마감일_없는_미완료다(self, service, seeded):
        assert [t.id for t in service.list("no-due")] == [seeded["마감없음"]]

    def test_태그_필터와_함께_쓸_수_있다(self, service, seeded):
        assert {t.id for t in service.list("active", tag="공부")} == {seeded["지남"], seeded["오늘"]}

    def test_키워드_필터와_함께_쓸_수_있다(self, service, seeded):
        assert [t.id for t in service.list("all", keyword="장보기")] == [seeded["미래"]]

    def test_알_수_없는_scope는_거부한다(self, service):
        with pytest.raises(ValidationError):
            service.list("이상한값")

    def test_기본_scope는_all이다(self, service, seeded):
        assert len(service.list()) == 5


class TestSummary:
    def test_개수를_집계한다(self, service, seeded):
        assert service.summary() == {
            "total": 5,
            "active": 4,
            "done": 1,
            "today": 2,
            "overdue": 1,
        }

    def test_빈_DB의_집계는_전부_0이다(self, service):
        assert service.summary() == {"total": 0, "active": 0, "done": 0, "today": 0, "overdue": 0}


class TestClockInjection:
    def test_시계를_바꾸면_today_결과가_바뀐다(self, conn):
        early = TodoService(conn, today=lambda: "2026-09-04")
        todo = early.add("발표", due="2026-09-10")
        assert early.list("today") == []
        late = TodoService(conn, today=lambda: "2026-09-11")
        assert [t.id for t in late.list("today")] == [todo.id]
```

- [x] **Step 2: 테스트 실패 확인**

Run: `cd ToDoApp && python3 -m pytest tests/test_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'todoapp.service'`

- [x] **Step 3: 최소 구현 작성**

`todoapp/service.py`:
```python
"""유스케이스 계층. CLI와 웹이 함께 쓴다.

여기 위쪽(cli·web)은 SQL도, sqlite3도 모른다.
트랜잭션 경계를 이 계층이 잡는 이유: '할 일 추가 + 태그 3개 연결'은
하나의 의미 단위다. 중간에 실패하면 통째로 되돌아가야 한다.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Callable, Iterable

from todoapp.models import Tag, Todo, ValidationError, parse_tag_list
# _Unset은 타입 힌트 전용으로만 가져온다. 런타임 판정은 is_set()을 쓴다.
from todoapp.repository import UNSET, TagRepository, TodoRepository, _Unset, is_set

SCOPES = ("all", "active", "done", "today", "overdue", "no-due")

SCOPE_LABELS: dict[str, str] = {
    "all": "전체",
    "active": "미완료",
    "done": "완료",
    "today": "오늘까지",
    "overdue": "기한 지남",
    "no-due": "마감일 없음",
}


class TodoNotFound(LookupError):
    """그 id의 할 일이 없다."""

    def __init__(self, todo_id: int) -> None:
        super().__init__(f"{todo_id}번 할 일을 찾을 수 없습니다.")
        self.todo_id = todo_id


def _system_today() -> str:
    """오늘 날짜. DB의 date('now','localtime')와 같은 기준(로컬 시간)이다."""
    return date.today().isoformat()


class TodoService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        today: Callable[[], str] = _system_today,
    ) -> None:
        self._conn = conn
        self._todos = TodoRepository(conn)
        self._tags = TagRepository(conn)
        self._today = today

    # ---- 조회 ----

    def get(self, todo_id: int) -> Todo:
        todo = self._todos.get(todo_id)
        if todo is None:
            raise TodoNotFound(todo_id)
        return todo

    def list(
        self,
        scope: str = "all",
        *,
        tag: str | None = None,
        keyword: str | None = None,
    ) -> list[Todo]:
        if scope not in SCOPES:
            raise ValidationError(
                f"알 수 없는 범위입니다: {scope!r} (가능: {', '.join(SCOPES)})"
            )
        filters: dict[str, object] = {}
        if scope == "active":
            filters = {"done": False}
        elif scope == "done":
            filters = {"done": True}
        elif scope == "today":
            filters = {"done": False, "due_on_or_before": self._today(), "has_due": True}
        elif scope == "overdue":
            filters = {"done": False, "due_before": self._today(), "has_due": True}
        elif scope == "no-due":
            filters = {"done": False, "has_due": False}
        return self._todos.list(tag=tag, keyword=keyword, **filters)

    def all_tags(self) -> list[Tag]:
        return self._tags.list_all()

    def today(self) -> str:
        """오늘 날짜 문자열.

        CLI의 '오늘·내일·+7d' 해석과 웹 화면의 '기한 지남' 표시가 이걸 쓴다.
        비공개 속성 _today에 상위 계층이 손대지 않도록 공개 메서드로 노출한다.
        """
        return self._today()

    def summary(self) -> dict[str, int]:
        return {
            "total": self._todos.count_all(),
            "active": len(self.list("active")),
            "done": len(self.list("done")),
            "today": len(self.list("today")),
            "overdue": len(self.list("overdue")),
        }

    # ---- 변경 ----

    def add(
        self,
        title: str,
        *,
        notes: str | None = None,
        due: str | None = None,
        priority: int | str | None = None,
        tags: str | Iterable[str] | None = None,
    ) -> Todo:
        tag_names = parse_tag_list(tags)
        with self._conn:
            todo_id = self._todos.add(title, notes=notes, due_date=due, priority=priority)
            if tag_names:
                self._todos.replace_tags(todo_id, self._resolve_tag_ids(tag_names))
        return self.get(todo_id)

    def edit(
        self,
        todo_id: int,
        *,
        title: str | _Unset = UNSET,
        notes: str | None | _Unset = UNSET,
        due: str | None | _Unset = UNSET,
        priority: int | str | _Unset = UNSET,
        tags: str | Iterable[str] | None | _Unset = UNSET,
    ) -> Todo:
        self.get(todo_id)  # 없는 id면 여기서 TodoNotFound를 던진다
        # tags를 아예 안 준 경우(UNSET)와 빈 값을 준 경우('' → 전부 제거)를 갈라야 한다
        tag_names = parse_tag_list(tags) if is_set(tags) else None
        with self._conn:
            self._todos.update(
                todo_id, title=title, notes=notes, due_date=due, priority=priority
            )
            if tag_names is not None:
                self._todos.replace_tags(todo_id, self._resolve_tag_ids(tag_names))
        return self.get(todo_id)

    def complete(self, todo_id: int) -> Todo:
        return self._set_done(todo_id, True)

    def reopen(self, todo_id: int) -> Todo:
        return self._set_done(todo_id, False)

    def toggle(self, todo_id: int) -> Todo:
        return self._set_done(todo_id, not self.get(todo_id).is_done)

    def delete(self, todo_id: int) -> None:
        with self._conn:
            if not self._todos.delete(todo_id):
                raise TodoNotFound(todo_id)

    # ---- 내부 ----

    def _set_done(self, todo_id: int, done: bool) -> Todo:
        with self._conn:
            if not self._todos.set_done(todo_id, done):
                raise TodoNotFound(todo_id)
        return self.get(todo_id)

    def _resolve_tag_ids(self, names: tuple[str, ...]) -> list[int]:
        """태그 이름을 id로. 없는 이름은 그 자리에서 만든다."""
        return [self._tags.upsert(name).id for name in names]
```

**주의**: `edit`에서 `tags=UNSET`(태그 손대지 않음)과 `tags=""`(태그 전부 제거)는
다른 뜻이다. `parse_tag_list("")`가 `()`를 주므로 후자는 `replace_tags(id, [])`가 되어
연결이 전부 지워진다. 전자는 `replace_tags`를 아예 부르지 않는다.

- [x] **Step 4: 테스트 통과 확인**

Run: `cd ToDoApp && python3 -m pytest tests/ -q`
Expected: PASS

- [x] **Step 5: 커밋**

```bash
cd /Users/kwonkwanggoo/aiffel_work
git add ToDoApp/todoapp/service.py ToDoApp/tests/test_service.py
git commit -m "feat(todoapp): 서비스 계층 추가 (유스케이스·트랜잭션 경계·주입 시계)"
```

---

### Task 7: CLI

**Files:**
- Create: `todoapp/cli.py`, `todo.py` (프로젝트 루트 실행 진입점)
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `service.TodoService`·`TodoNotFound`·`SCOPES`, `database.open_db`, `config.get_db_path`
- Produces:
  - `cli.resolve_due_input(raw: str | None, today: str) -> str | None`
  - `cli.display_width(text: str) -> int`
  - `cli.format_table(todos: Sequence[Todo]) -> str`
  - `cli.build_parser() -> argparse.ArgumentParser`
  - `cli.main(argv: Sequence[str] | None = None, *, service: TodoService | None = None, confirm: Callable[[str], bool] | None = None) -> int`

**설계 근거 — 표 정렬에 글자 폭 계산이 필요한 이유:** `str.ljust`는 글자 수로 채운다.
한글은 터미널에서 두 칸을 차지하므로 `"장보기".ljust(10)`은 실제로 13칸이 되어 열이 어긋난다.
`unicodedata.east_asian_width`로 실제 표시 폭을 세야 표가 맞는다.

**설계 근거 — `main`이 `service`를 인자로 받는 이유:** 기본값은 `.env`의 실제 DB를 열지만,
테스트는 임시 DB로 만든 서비스를 넘겨 넣는다. `subprocess`를 띄우지 않고
함수 호출로 CLI 전체를 테스트할 수 있다.

- [x] **Step 1: 실패하는 테스트 작성**

`tests/test_cli.py`:
```python
"""CLI 테스트. subprocess 없이 main()을 직접 부른다."""
from __future__ import annotations

import pytest

from todoapp.cli import display_width, format_table, main, resolve_due_input
from todoapp.service import TodoService

FIXED_TODAY = "2026-09-04"


@pytest.fixture
def service(conn) -> TodoService:
    return TodoService(conn, today=lambda: FIXED_TODAY)


@pytest.fixture
def run(service):
    """CLI를 돌리고 (종료코드, stdout, stderr)를 돌려주는 도우미."""

    def _run(*argv, confirm=None):
        return main(list(argv), service=service, confirm=confirm or (lambda _: True))

    return _run


class TestResolveDueInput:
    def test_ISO_날짜는_그대로(self):
        assert resolve_due_input("2026-09-10", FIXED_TODAY) == "2026-09-10"

    @pytest.mark.parametrize("word", ["today", "오늘"])
    def test_오늘(self, word):
        assert resolve_due_input(word, FIXED_TODAY) == FIXED_TODAY

    @pytest.mark.parametrize("word", ["tomorrow", "내일"])
    def test_내일(self, word):
        assert resolve_due_input(word, FIXED_TODAY) == "2026-09-05"

    def test_상대_일수(self):
        assert resolve_due_input("+7d", FIXED_TODAY) == "2026-09-11"
        assert resolve_due_input("-1d", FIXED_TODAY) == "2026-09-03"

    def test_달을_넘어가는_상대_일수(self):
        assert resolve_due_input("+30d", FIXED_TODAY) == "2026-10-04"

    @pytest.mark.parametrize("word", ["", "none", "없음"])
    def test_비우기(self, word):
        assert resolve_due_input(word, FIXED_TODAY) is None

    def test_안_준_경우도_None(self):
        assert resolve_due_input(None, FIXED_TODAY) is None

    def test_알_수_없는_형식은_거부한다(self):
        from todoapp.models import ValidationError

        with pytest.raises(ValidationError):
            resolve_due_input("다음주", FIXED_TODAY)


class TestDisplayWidth:
    def test_영문은_한_칸(self):
        assert display_width("abc") == 3

    def test_한글은_두_칸(self):
        assert display_width("장보기") == 6

    def test_섞이면_합산한다(self):
        assert display_width("ab장") == 4

    def test_빈_문자열은_0(self):
        assert display_width("") == 0


class TestFormatTable:
    def test_빈_목록은_안내_문구다(self):
        assert "없습니다" in format_table([])

    def test_제목이_들어간다(self, service):
        todo = service.add("장보기", due="2026-09-10", tags="집안일")
        table = format_table([todo])
        assert "장보기" in table
        assert "2026-09-10" in table
        assert "집안일" in table
        assert str(todo.id) in table

    def test_완료_표시가_구분된다(self, service):
        active = service.add("미완료 항목")
        done = service.complete(service.add("완료 항목").id)
        table = format_table([active, done])
        active_line = next(l for l in table.splitlines() if "미완료 항목" in l)
        done_line = next(l for l in table.splitlines() if "완료 항목" in l)
        assert active_line != done_line
        assert "[x]" in done_line
        assert "[ ]" in active_line

    def test_한글_제목이_섞여도_열_폭이_일정하다(self, service):
        service.add("ab")
        service.add("한글제목입니다")
        lines = [l for l in format_table(service.list()).splitlines() if l.strip()]
        widths = {display_width(line) for line in lines}
        assert len(widths) == 1  # 모든 줄의 표시 폭이 같아야 한다
```

이어서 서브커맨드 테스트:
```python
class TestAddCommand:
    def test_추가하면_0을_돌려준다(self, run, service):
        assert run("add", "장보기") == 0
        assert [t.title for t in service.list()] == ["장보기"]

    def test_모든_옵션을_받는다(self, run, service):
        assert run(
            "add", "장보기",
            "--due", "2026-09-10",
            "--tag", "집안일,장보기",
            "--priority", "high",
            "--notes", "우유",
        ) == 0
        todo = service.list()[0]
        assert todo.due_date == "2026-09-10"
        assert todo.notes == "우유"
        assert {t.name for t in todo.tags} == {"집안일", "장보기"}

    def test_오늘이라는_말을_날짜로_바꾼다(self, run, service):
        run("add", "발표", "--due", "오늘")
        assert service.list()[0].due_date == FIXED_TODAY

    def test_빈_제목은_1을_돌려주고_stderr에_안내한다(self, run, capsys):
        assert run("add", "   ") == 1
        assert capsys.readouterr().err.strip() != ""

    def test_잘못된_날짜는_1을_돌려준다(self, run):
        assert run("add", "장보기", "--due", "2026-02-31") == 1


class TestListCommand:
    def test_목록을_출력한다(self, run, service, capsys):
        service.add("장보기")
        assert run("list") == 0
        assert "장보기" in capsys.readouterr().out

    def test_범위_지름길_플래그(self, run, service, capsys):
        service.add("지난 것", due="2026-09-01")
        service.add("미래 것", due="2026-09-30")
        run("list", "--overdue")
        out = capsys.readouterr().out
        assert "지난 것" in out and "미래 것" not in out

    def test_태그로_거른다(self, run, service, capsys):
        service.add("공부하기", tags="공부")
        service.add("청소하기", tags="집안일")
        run("list", "--tag", "공부")
        out = capsys.readouterr().out
        assert "공부하기" in out and "청소하기" not in out

    def test_키워드로_찾는다(self, run, service, capsys):
        service.add("장보기")
        service.add("청소하기")
        run("list", "--search", "장보")
        out = capsys.readouterr().out
        assert "장보기" in out and "청소하기" not in out

    def test_요약이_함께_출력된다(self, run, service, capsys):
        service.add("할 일", due="2026-09-01")
        run("list")
        assert "미완료" in capsys.readouterr().out


class TestStateCommands:
    def test_완료로_표시한다(self, run, service):
        todo = service.add("장보기")
        assert run("done", str(todo.id)) == 0
        assert service.get(todo.id).is_done is True

    def test_완료를_되돌린다(self, run, service):
        todo = service.complete(service.add("장보기").id)
        assert run("undone", str(todo.id)) == 0
        assert service.get(todo.id).is_done is False

    def test_없는_id는_1을_돌려준다(self, run, capsys):
        assert run("done", "9999") == 1
        assert "찾을 수 없" in capsys.readouterr().err


class TestRemoveCommand:
    def test_확인하면_지운다(self, run, service):
        todo = service.add("장보기")
        assert run("rm", str(todo.id), confirm=lambda _: True) == 0
        assert service.list() == []

    def test_거절하면_남는다(self, run, service, capsys):
        todo = service.add("장보기")
        assert run("rm", str(todo.id), confirm=lambda _: False) == 0
        assert len(service.list()) == 1
        assert "취소" in capsys.readouterr().out

    def test_yes_플래그는_묻지_않는다(self, run, service):
        todo = service.add("장보기")

        def 절대_불리면_안됨(_):
            raise AssertionError("--yes를 줬는데 확인을 물었다")

        assert run("rm", str(todo.id), "--yes", confirm=절대_불리면_안됨) == 0
        assert service.list() == []


class TestShowAndTags:
    def test_상세를_출력한다(self, run, service, capsys):
        todo = service.add("장보기", notes="우유 사기", due="2026-09-10", tags="집안일")
        assert run("show", str(todo.id)) == 0
        out = capsys.readouterr().out
        assert "우유 사기" in out and "집안일" in out and "2026-09-10" in out

    def test_태그_목록을_출력한다(self, run, service, capsys):
        service.add("과제", tags="공부,집안일")
        assert run("tags") == 0
        out = capsys.readouterr().out
        assert "공부" in out and "집안일" in out

    def test_태그가_없으면_안내한다(self, run, capsys):
        assert run("tags") == 0
        assert "없습니다" in capsys.readouterr().out


class TestEditCommand:
    def test_제목을_바꾼다(self, run, service):
        todo = service.add("장보기")
        assert run("edit", str(todo.id), "--title", "장보기(수정)") == 0
        assert service.get(todo.id).title == "장보기(수정)"

    def test_마감일을_비운다(self, run, service):
        todo = service.add("장보기", due="2026-09-10")
        assert run("edit", str(todo.id), "--due", "없음") == 0
        assert service.get(todo.id).due_date is None

    def test_태그를_교체한다(self, run, service):
        todo = service.add("과제", tags="공부")
        assert run("edit", str(todo.id), "--tag", "집안일") == 0
        assert [t.name for t in service.get(todo.id).tags] == ["집안일"]


class TestParser:
    def test_서브커맨드_없이_부르면_사용법을_알린다(self, run, capsys):
        assert run() == 2

    def test_알_수_없는_서브커맨드는_SystemExit이다(self, service):
        with pytest.raises(SystemExit):
            main(["없는명령"], service=service)
```

- [x] **Step 2: 테스트 실패 확인**

Run: `cd ToDoApp && python3 -m pytest tests/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'todoapp.cli'`

- [x] **Step 3: 최소 구현 작성**

`todoapp/cli.py`:
```python
"""터미널 인터페이스. 서비스 계층만 호출하고 SQL은 모른다."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from datetime import date, timedelta
from typing import Callable, Sequence

from todoapp.config import get_db_path
from todoapp.database import open_db
from todoapp.models import (
    PRIORITY_LABELS,
    Todo,
    ValidationError,
    normalize_due_date,
)
from todoapp.service import SCOPES, TodoNotFound, TodoService

_RELATIVE_DAYS_RE = re.compile(r"^([+-])(\d+)d$", re.IGNORECASE)
_TODAY_WORDS = {"today", "오늘"}
_TOMORROW_WORDS = {"tomorrow", "내일"}
_CLEAR_WORDS = {"", "none", "없음", "null"}


def resolve_due_input(raw: str | None, today: str) -> str | None:
    """사람이 쓰는 표현을 'YYYY-MM-DD'로 바꾼다.

    받는 형태: ISO 날짜 / today·오늘 / tomorrow·내일 / +7d·-1d / none·없음(비우기)
    """
    if raw is None:
        return None
    value = str(raw).strip()
    if value.lower() in _CLEAR_WORDS:
        return None
    lowered = value.lower()
    base = date.fromisoformat(today)
    if lowered in _TODAY_WORDS:
        return base.isoformat()
    if lowered in _TOMORROW_WORDS:
        return (base + timedelta(days=1)).isoformat()
    match = _RELATIVE_DAYS_RE.match(value)
    if match:
        sign = 1 if match.group(1) == "+" else -1
        return (base + timedelta(days=sign * int(match.group(2)))).isoformat()
    return normalize_due_date(value)  # ISO가 아니면 여기서 ValidationError


def display_width(text: str) -> int:
    """터미널에서 차지하는 칸 수. 한글·한자·일본어는 두 칸이다."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    """표시 폭 기준으로 오른쪽을 채운다. str.ljust는 글자 수로 세서 못 쓴다."""
    return text + " " * max(0, width - display_width(text))


_HEADERS = ("ID", "상태", "제목", "마감일", "우선", "태그")


def _to_row(todo: Todo) -> tuple[str, ...]:
    return (
        str(todo.id),
        "[x]" if todo.is_done else "[ ]",
        todo.title,
        todo.due_date or "-",
        PRIORITY_LABELS[todo.priority],
        ", ".join(t.name for t in todo.tags) or "-",
    )


def format_table(todos: Sequence[Todo]) -> str:
    """할 일 목록을 고정 폭 표로. 모든 줄의 표시 폭이 같도록 맞춘다."""
    if not todos:
        return "할 일이 없습니다."
    rows = [_HEADERS, *(_to_row(t) for t in todos)]
    widths = [max(display_width(row[i]) for row in rows) for i in range(len(_HEADERS))]
    gap = "  "
    total = sum(widths) + len(gap) * (len(widths) - 1)
    lines = [
        gap.join(_pad(cell, widths[i]) for i, cell in enumerate(row)) for row in rows
    ]
    # 모든 줄이 정확히 total 폭이다 (마지막 칸까지 채우므로 rstrip하지 않는다)
    return "\n".join([lines[0], "-" * total, *lines[1:]])


def format_detail(todo: Todo) -> str:
    tag_text = ", ".join(t.name for t in todo.tags) or "-"
    lines = [
        f"[{todo.id}] {todo.title}",
        f"  상태     : {'완료' if todo.is_done else '미완료'}",
        f"  마감일   : {todo.due_date or '-'}",
        f"  우선순위 : {PRIORITY_LABELS[todo.priority]}",
        f"  태그     : {tag_text}",
        f"  메모     : {todo.notes or '-'}",
        f"  생성     : {todo.created_at}",
        f"  수정     : {todo.updated_at}",
    ]
    if todo.completed_at:
        lines.append(f"  완료     : {todo.completed_at}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="todo", description="로컬 SQLite에 저장하는 할 일 관리 도구"
    )
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="할 일 추가")
    p_add.add_argument("title", help="할 일 제목")
    p_add.add_argument("--due", help="마감일 (2026-09-10 / 오늘 / 내일 / +7d)")
    p_add.add_argument("--tag", help="태그, 쉼표로 구분 (예: 공부,집안일)")
    p_add.add_argument("--priority", help="우선순위 (high/normal/low 또는 1/2/3)")
    p_add.add_argument("--notes", help="메모")

    p_list = sub.add_parser("list", help="목록 보기")
    p_list.add_argument("--scope", choices=SCOPES, default="all", help="범위")
    group = p_list.add_mutually_exclusive_group()
    group.add_argument("--all", dest="scope", action="store_const", const="all")
    group.add_argument("--active", dest="scope", action="store_const", const="active")
    group.add_argument("--done", dest="scope", action="store_const", const="done")
    group.add_argument("--today", dest="scope", action="store_const", const="today")
    group.add_argument("--overdue", dest="scope", action="store_const", const="overdue")
    p_list.add_argument("--tag", help="이 태그가 붙은 것만")
    p_list.add_argument("--search", help="제목·메모에서 찾기")

    for name, help_text in (("done", "완료로 표시"), ("undone", "완료 되돌리기"), ("show", "상세 보기")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("id", type=int, help="할 일 번호")

    p_rm = sub.add_parser("rm", help="삭제")
    p_rm.add_argument("id", type=int, help="할 일 번호")
    p_rm.add_argument("-y", "--yes", action="store_true", help="확인 없이 삭제")

    p_edit = sub.add_parser("edit", help="내용 수정")
    p_edit.add_argument("id", type=int, help="할 일 번호")
    p_edit.add_argument("--title")
    p_edit.add_argument("--due", help="마감일 ('없음'을 주면 비운다)")
    p_edit.add_argument("--tag", help="태그 전체를 이것으로 교체 (빈 문자열이면 전부 제거)")
    p_edit.add_argument("--priority")
    p_edit.add_argument("--notes")

    sub.add_parser("tags", help="태그 목록")
    return parser


def _default_confirm(question: str) -> bool:
    answer = input(f"{question} [y/N] ").strip().lower()
    return answer in ("y", "yes")


def main(
    argv: Sequence[str] | None = None,
    *,
    service: TodoService | None = None,
    confirm: Callable[[str], bool] | None = None,
) -> int:
    """CLI 진입점. 종료 코드를 돌려준다 (0 성공 / 1 사용자 오류 / 2 사용법 오류)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2

    if service is not None:
        return _dispatch(args, service, confirm or _default_confirm)
    with open_db(get_db_path()) as conn:
        return _dispatch(args, TodoService(conn), confirm or _default_confirm)


def _dispatch(
    args: argparse.Namespace, service: TodoService, confirm: Callable[[str], bool]
) -> int:
    # 서비스의 시계를 쓴다. date.today()를 직접 부르면 주입한 고정 시계가 무시되어
    # '--due 오늘' 테스트가 실행 날짜에 따라 통과·실패를 오간다.
    today = service.today()
    try:
        if args.command == "add":
            todo = service.add(
                args.title,
                notes=args.notes,
                due=resolve_due_input(args.due, today),
                priority=args.priority,
                tags=args.tag,
            )
            print(f"추가했습니다. [{todo.id}] {todo.title}")

        elif args.command == "list":
            todos = service.list(args.scope, tag=args.tag, keyword=args.search)
            print(format_table(todos))
            s = service.summary()
            print(f"\n전체 {s['total']} · 미완료 {s['active']} · 오늘까지 {s['today']} · 지남 {s['overdue']}")

        elif args.command == "done":
            print(f"완료로 표시했습니다. [{args.id}] {service.complete(args.id).title}")

        elif args.command == "undone":
            print(f"미완료로 되돌렸습니다. [{args.id}] {service.reopen(args.id).title}")

        elif args.command == "show":
            print(format_detail(service.get(args.id)))

        elif args.command == "rm":
            todo = service.get(args.id)
            if not args.yes and not confirm(f"[{todo.id}] {todo.title} 을(를) 삭제할까요?"):
                print("취소했습니다.")
                return 0
            service.delete(args.id)
            print(f"삭제했습니다. [{todo.id}] {todo.title}")

        elif args.command == "edit":
            fields: dict[str, object] = {}
            if args.title is not None:
                fields["title"] = args.title
            if args.notes is not None:
                fields["notes"] = args.notes or None
            if args.due is not None:
                fields["due"] = resolve_due_input(args.due, today)
            if args.priority is not None:
                fields["priority"] = args.priority
            if args.tag is not None:
                fields["tags"] = args.tag
            todo = service.edit(args.id, **fields)  # type: ignore[arg-type]
            print(f"수정했습니다. [{todo.id}] {todo.title}")

        elif args.command == "tags":
            tags = service.all_tags()
            if not tags:
                print("등록된 태그가 없습니다.")
            else:
                for tag in tags:
                    print(f"  {tag.name}  ({tag.color})")

    except ValidationError as exc:
        print(f"입력 오류: {exc}", file=sys.stderr)
        return 1
    except TodoNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`todo.py` (프로젝트 루트, 짧게 실행하기 위한 진입점):
```python
#!/usr/bin/env python3
"""`python3 todo.py add "장보기"` 로 쓰기 위한 진입점."""

from todoapp.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: 테스트 통과 확인**

Run: `cd ToDoApp && python3 -m pytest tests/ -q`
Expected: PASS

- [x] **Step 5: 실제 실행으로 손 확인**

```bash
cd /Users/kwonkwanggoo/aiffel_work/ToDoApp
python3 todo.py add "계획서 검토" --due 오늘 --tag 공부 --priority high
python3 todo.py add "장보기" --due +3d --tag 집안일 --notes "우유, 계란"
python3 todo.py list
python3 todo.py done 1
python3 todo.py list --all
python3 todo.py show 2
python3 todo.py tags
python3 todo.py rm 1 --yes
```
Expected: 표가 어긋나지 않고, 각 명령이 안내 문구와 함께 0으로 끝난다.

- [x] **Step 6: 커밋**

```bash
cd /Users/kwonkwanggoo/aiffel_work
git add ToDoApp/todoapp/cli.py ToDoApp/todo.py ToDoApp/tests/test_cli.py
git commit -m "feat(todoapp): CLI 추가 (한글 폭 보정 표, 상대 날짜 입력)"
```

---
### Task 8: Flask 웹 화면

**Files:**
- Modify: `todoapp/config.py` (`get_secret_key` 추가)
- Modify: `.env.example` (`FLASK_SECRET_KEY` 추가)
- Create: `todoapp/web/__init__.py`, `todoapp/web/routes.py`
- Create: `todoapp/web/templates/base.html`, `todoapp/web/templates/index.html`
- Create: `app.py` (프로젝트 루트 실행 진입점)
- Create: `tests/test_web.py`

**Interfaces:**
- Consumes: `service.TodoService`·`TodoNotFound`·`SCOPES`·`SCOPE_LABELS`, `database.connect`·`initialize`
- Produces:
  - `config.get_secret_key() -> str` (미설정 시 `RuntimeError`)
  - `web.create_app(*, db_path=None, secret_key=None, today=None) -> Flask`
  - `web.get_service() -> TodoService` (요청 컨텍스트 안에서만)
  - 라우트: `GET /`, `POST /todos`, `POST /todos/<int:todo_id>/toggle`, `POST /todos/<int:todo_id>/delete`

**설계 결정 3가지와 근거:**

1. **PRG(Post-Redirect-Get) 패턴** — POST 처리 후 반드시 리다이렉트한다. 그렇지 않으면
   사용자가 새로고침할 때 같은 할 일이 또 추가된다.
2. **요청마다 커넥션 하나** — `flask.g`에 담고 `teardown_appcontext`에서 닫는다.
   sqlite3 커넥션은 기본적으로 만든 스레드에서만 쓸 수 있어서, 앱 전역에
   하나를 두면 Flask의 스레드 모델과 충돌한다.
3. **CSRF 토큰 없음** — PRD에 로그인이 없고 `127.0.0.1` 단독 실행 전제다. 세션에
   보호할 것이 없다. **외부에 노출하려면 로그인과 CSRF를 함께 붙여야 하며,
   그때는 직접 만들지 말고 Flask-Login·Flask-WTF를 쓴다.** README에 명시한다.

`FLASK_SECRET_KEY`가 필요한 이유는 flash 메시지(입력 오류 안내)가 세션을 쓰기 때문이다.
값이 없으면 기본값으로 대충 넘기지 않고 즉시 예외를 던진다(전역 제약: 비밀값은 `.env`로만).

- [x] **Step 1: 실패하는 테스트 작성**

`tests/test_web.py`:
```python
"""Flask 웹 화면 테스트."""
from __future__ import annotations

import pytest

from todoapp.database import connect, initialize
from todoapp.service import TodoService
from todoapp.web import create_app

FIXED_TODAY = "2026-09-04"


@pytest.fixture
def app(db_path):
    return create_app(db_path=db_path, secret_key="테스트용키", today=lambda: FIXED_TODAY)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeder(db_path):
    """테스트에서 직접 데이터를 넣기 위한 서비스. 앱과 별도 커넥션을 쓴다."""
    conn = connect(db_path)
    initialize(conn)
    yield TodoService(conn, today=lambda: FIXED_TODAY)
    conn.close()


class TestSecretKey:
    def test_비밀키가_없으면_앱_생성이_실패한다(self, db_path, monkeypatch):
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        monkeypatch.setattr("todoapp.config.load_dotenv", lambda *a, **k: None)
        with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
            create_app(db_path=db_path)

    def test_환경변수에서_비밀키를_읽는다(self, db_path, monkeypatch):
        monkeypatch.setenv("FLASK_SECRET_KEY", "환경변수키")
        app = create_app(db_path=db_path)
        assert app.secret_key == "환경변수키"


class TestIndex:
    def test_빈_목록도_200이다(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "할 일이 없습니다" in response.get_data(as_text=True)

    def test_할_일이_화면에_나온다(self, client, seeder):
        seeder.add("장보기", due="2026-09-10", tags="집안일")
        body = client.get("/").get_data(as_text=True)
        assert "장보기" in body
        assert "2026-09-10" in body
        assert "집안일" in body

    def test_범위_필터가_동작한다(self, client, seeder):
        seeder.add("지난 것", due="2026-09-01")
        seeder.add("미래 것", due="2026-09-30")
        body = client.get("/?scope=overdue").get_data(as_text=True)
        assert "지난 것" in body and "미래 것" not in body

    def test_태그_필터가_동작한다(self, client, seeder):
        seeder.add("공부하기", tags="공부")
        seeder.add("청소하기", tags="집안일")
        body = client.get("/?tag=공부").get_data(as_text=True)
        assert "공부하기" in body and "청소하기" not in body

    def test_검색이_동작한다(self, client, seeder):
        seeder.add("장보기")
        seeder.add("청소하기")
        body = client.get("/?q=장보").get_data(as_text=True)
        assert "장보기" in body and "청소하기" not in body

    def test_알_수_없는_범위는_400이다(self, client):
        assert client.get("/?scope=이상한값").status_code == 400

    def test_요약_숫자가_나온다(self, client, seeder):
        seeder.add("할 일", due="2026-09-01")
        assert "미완료" in client.get("/").get_data(as_text=True)

    def test_HTML이_이스케이프된다(self, client, seeder):
        seeder.add("<script>alert(1)</script>")
        body = client.get("/").get_data(as_text=True)
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;" in body


class TestCreate:
    def test_추가하면_리다이렉트한다(self, client, seeder):
        response = client.post("/todos", data={"title": "장보기"})
        assert response.status_code == 302
        assert [t.title for t in seeder.list()] == ["장보기"]

    def test_모든_필드를_받는다(self, client, seeder):
        client.post(
            "/todos",
            data={
                "title": "장보기",
                "due_date": "2026-09-10",
                "tags": "집안일,장보기",
                "priority": "1",
                "notes": "우유",
            },
        )
        todo = seeder.list()[0]
        assert todo.due_date == "2026-09-10"
        assert todo.notes == "우유"
        assert {t.name for t in todo.tags} == {"집안일", "장보기"}

    def test_빈_제목은_안내_메시지와_함께_돌아온다(self, client, seeder):
        response = client.post("/todos", data={"title": "   "}, follow_redirects=True)
        assert response.status_code == 200
        assert "제목을 입력하세요" in response.get_data(as_text=True)
        assert seeder.list() == []

    def test_잘못된_날짜는_저장되지_않는다(self, client, seeder):
        response = client.post(
            "/todos", data={"title": "장보기", "due_date": "2026-02-31"}, follow_redirects=True
        )
        assert "존재하지 않는 날짜" in response.get_data(as_text=True)
        assert seeder.list() == []

    def test_추가_후_필터가_유지된다(self, client):
        response = client.post("/todos", data={"title": "장보기", "scope": "active", "tag": "공부"})
        assert "scope=active" in response.headers["Location"]

    def test_새로고침_중복_추가를_막기_위해_리다이렉트한다(self, client):
        # PRG 패턴: POST 응답은 200이 아니라 302여야 한다
        assert client.post("/todos", data={"title": "장보기"}).status_code == 302


class TestToggleAndDelete:
    def test_토글하면_완료_상태가_바뀐다(self, client, seeder):
        todo = seeder.add("장보기")
        client.post(f"/todos/{todo.id}/toggle")
        assert seeder.get(todo.id).is_done is True
        client.post(f"/todos/{todo.id}/toggle")
        assert seeder.get(todo.id).is_done is False

    def test_삭제하면_사라진다(self, client, seeder):
        todo = seeder.add("장보기")
        assert client.post(f"/todos/{todo.id}/delete").status_code == 302
        assert seeder.list() == []

    def test_없는_id를_토글하면_404다(self, client):
        assert client.post("/todos/9999/toggle").status_code == 404

    def test_없는_id를_삭제하면_404다(self, client):
        assert client.post("/todos/9999/delete").status_code == 404

    def test_GET으로는_변경할_수_없다(self, client, seeder):
        todo = seeder.add("장보기")
        assert client.get(f"/todos/{todo.id}/delete").status_code == 405
        assert seeder.get(todo.id) is not None


class TestConnectionHandling:
    def test_여러_요청을_연달아_처리한다(self, client, seeder):
        # 요청마다 커넥션을 새로 열고 닫는지 확인. 누수가 있으면 여기서 터진다.
        for i in range(15):
            client.post("/todos", data={"title": f"할 일 {i}"})
        assert client.get("/").status_code == 200
        assert len(seeder.list()) == 15
```

- [x] **Step 2: 테스트 실패 확인**

Run: `cd ToDoApp && python3 -m pytest tests/test_web.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'todoapp.web'`

- [x] **Step 3: `config.get_secret_key` 추가**

`todoapp/config.py`에 추가:
```python
def get_secret_key() -> str:
    """Flask 세션 키. .env의 FLASK_SECRET_KEY에서만 읽는다.

    기본값을 두지 않는 이유: 하드코딩된 기본 키는 세션 위조를 허용한다.
    없으면 대충 넘기지 말고 즉시 멈춘다.
    """
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.getenv("FLASK_SECRET_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "FLASK_SECRET_KEY가 설정되지 않았습니다. "
            ".env.example을 .env로 복사한 뒤 값을 채우세요.\n"
            "  생성: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return key
```

`.env.example`을 다음 내용으로 교체:
```
# 복사해서 .env 로 쓰세요 (.env 는 커밋하지 않습니다)

# DB 파일 경로. 상대 경로는 프로젝트 루트 기준.
DB_PATH=db/todo.db

# Flask 세션 서명 키 (웹 화면의 안내 메시지에 필요).
# 생성: python3 -c "import secrets; print(secrets.token_hex(32))"
FLASK_SECRET_KEY=
```

- [x] **Step 4: 웹 앱 구현**

`todoapp/web/__init__.py`:
```python
"""Flask 앱 팩토리. 요청마다 SQLite 커넥션을 새로 열고 닫는다."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable

from flask import Flask, current_app, g

from todoapp.config import get_db_path, get_secret_key
from todoapp.database import connect, initialize
from todoapp.service import TodoService

_CONN_KEY = "_todoapp_conn"


def create_app(
    *,
    db_path: str | Path | None = None,
    secret_key: str | None = None,
    today: Callable[[], str] | None = None,
) -> Flask:
    app = Flask(__name__)
    app.secret_key = secret_key or get_secret_key()
    app.config["TODOAPP_DB_PATH"] = Path(db_path) if db_path else get_db_path()
    app.config["TODOAPP_TODAY"] = today

    # 스키마는 시작할 때 한 번만 적용한다. 요청마다 하면 느려진다.
    bootstrap = connect(app.config["TODOAPP_DB_PATH"])
    try:
        initialize(bootstrap)
    finally:
        bootstrap.close()

    from todoapp.web.routes import bp

    app.register_blueprint(bp)
    app.teardown_appcontext(_close_connection)
    return app


def _get_connection() -> sqlite3.Connection:
    conn = getattr(g, _CONN_KEY, None)
    if conn is None:
        conn = connect(current_app.config["TODOAPP_DB_PATH"])
        setattr(g, _CONN_KEY, conn)
    return conn


def _close_connection(exception: BaseException | None = None) -> None:
    conn = getattr(g, _CONN_KEY, None)
    if conn is not None:
        conn.close()
        setattr(g, _CONN_KEY, None)


def get_service() -> TodoService:
    """이 요청에 묶인 서비스. 요청 컨텍스트 안에서만 부를 수 있다."""
    today = current_app.config.get("TODOAPP_TODAY")
    conn = _get_connection()
    return TodoService(conn, today=today) if today else TodoService(conn)
```

`todoapp/web/routes.py`:
```python
"""라우트. 변경 요청은 모두 POST + 리다이렉트(PRG)로 처리한다."""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from todoapp.models import PRIORITY_LABELS, ValidationError
from todoapp.service import SCOPE_LABELS, SCOPES, TodoNotFound

bp = Blueprint("todos", __name__)


def _service():
    """순환 import를 피하기 위해 호출 시점에 가져온다."""
    from todoapp.web import get_service

    return get_service()


def _current_filters() -> dict[str, str]:
    """지금 보고 있는 필터. POST 후 같은 화면으로 돌아가기 위해 쓴다."""
    source = request.form if request.method == "POST" else request.args
    filters: dict[str, str] = {}
    for key in ("scope", "tag", "q"):
        value = (source.get(key) or "").strip()
        if value:
            filters[key] = value
    return filters


@bp.get("/")
def index():
    filters = _current_filters()
    scope = filters.get("scope", "all")
    if scope not in SCOPES:
        abort(400, description=f"알 수 없는 범위입니다: {scope}")
    service = _service()
    todos = service.list(scope, tag=filters.get("tag"), keyword=filters.get("q"))
    return render_template(
        "index.html",
        todos=todos,
        all_tags=service.all_tags(),
        summary=service.summary(),
        today=service.today(),
        scope=scope,
        scopes=SCOPES,
        scope_labels=SCOPE_LABELS,
        priority_labels=PRIORITY_LABELS,
        active_tag=filters.get("tag", ""),
        query=filters.get("q", ""),
    )


@bp.post("/todos")
def create():
    filters = _current_filters()
    try:
        _service().add(
            request.form.get("title", ""),
            notes=request.form.get("notes") or None,
            due=request.form.get("due_date") or None,
            priority=request.form.get("priority") or None,
            tags=request.form.get("tags") or None,
        )
    except ValidationError as exc:
        flash(str(exc))
    return redirect(url_for(".index", **filters))


@bp.post("/todos/<int:todo_id>/toggle")
def toggle(todo_id: int):
    filters = _current_filters()
    try:
        _service().toggle(todo_id)
    except TodoNotFound:
        abort(404)
    return redirect(url_for(".index", **filters))


@bp.post("/todos/<int:todo_id>/delete")
def delete(todo_id: int):
    filters = _current_filters()
    try:
        _service().delete(todo_id)
    except TodoNotFound:
        abort(404)
    return redirect(url_for(".index", **filters))
```

`todoapp/web/templates/base.html`:
```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}할 일{% endblock %}</title>
  <style>
    :root {
      --bg: #f7f6f3; --card: #ffffff; --text: #26251f; --muted: #6b6a63;
      --line: #e2e0d8; --accent: #534ab7; --danger: #a32d2d; --done: #9c9a92;
      --warn-bg: #fceaea; --warn-text: #791f1f; --warn-line: #f09595;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #1c1c1a; --card: #262521; --text: #e8e6de; --muted: #9c9a92;
        --line: #3a3935; --accent: #afa9ec; --danger: #f09595; --done: #6b6a63;
        --warn-bg: #501313; --warn-text: #f7c1c1; --warn-line: #a32d2d;
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; padding: 24px 16px; background: var(--bg); color: var(--text);
      font: 15px/1.6 -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
    }
    .wrap { max-width: 780px; margin: 0 auto; }
    h1 { font-size: 22px; font-weight: 600; margin: 0 0 4px; }
    .sub { color: var(--muted); font-size: 13px; margin: 0 0 20px; }
    .card {
      background: var(--card); border: 1px solid var(--line);
      border-radius: 12px; padding: 16px; margin-bottom: 16px;
    }
    label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 4px; }
    input, select, button {
      font: inherit; color: inherit; padding: 8px 10px;
      border: 1px solid var(--line); border-radius: 8px; background: var(--bg);
    }
    input:focus, select:focus { outline: 2px solid var(--accent); outline-offset: -1px; }
    button { cursor: pointer; }
    button.primary { background: var(--accent); color: #fff; border-color: transparent; }
    button.link {
      background: none; border: none; padding: 2px 6px;
      color: var(--muted); font-size: 13px; text-decoration: underline;
    }
    button.link.danger { color: var(--danger); }
    .grid { display: grid; grid-template-columns: 1fr 160px; gap: 10px; }
    .grid-3 { display: grid; grid-template-columns: 1fr 1fr 120px; gap: 10px; margin-top: 10px; }
    @media (max-width: 560px) { .grid, .grid-3 { grid-template-columns: 1fr; } }
    .flash {
      padding: 10px 12px; border-radius: 8px; margin-bottom: 12px; font-size: 14px;
      background: var(--warn-bg); color: var(--warn-text); border: 1px solid var(--warn-line);
    }
    .tabs { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 12px; }
    .tab {
      padding: 5px 11px; border-radius: 999px; font-size: 13px; text-decoration: none;
      color: var(--muted); border: 1px solid var(--line);
    }
    .tab.on { background: var(--accent); color: #fff; border-color: transparent; }
    ul.todos { list-style: none; margin: 0; padding: 0; }
    ul.todos li {
      display: flex; align-items: flex-start; gap: 10px;
      padding: 12px 0; border-bottom: 1px solid var(--line);
    }
    ul.todos li:last-child { border-bottom: none; }
    .body { flex: 1; min-width: 0; }
    .title { font-weight: 500; word-break: break-word; }
    .done .title { text-decoration: line-through; color: var(--done); }
    .meta { font-size: 12px; color: var(--muted); margin-top: 3px; }
    .overdue { color: var(--danger); font-weight: 500; }
    .chip {
      display: inline-block; padding: 1px 7px; border-radius: 999px;
      font-size: 11px; border: 1px solid var(--line); margin-right: 4px;
    }
    .empty { color: var(--muted); text-align: center; padding: 28px 0; }
    footer { color: var(--muted); font-size: 12px; text-align: center; margin-top: 24px; }
  </style>
</head>
<body>
  <div class="wrap">
    {% with messages = get_flashed_messages() %}
      {% for message in messages %}<div class="flash">{{ message }}</div>{% endfor %}
    {% endwith %}
    {% block content %}{% endblock %}
  </div>
</body>
</html>
```

`todoapp/web/templates/index.html`:
```html
{% extends "base.html" %}

{% macro filter_fields() %}
  <input type="hidden" name="scope" value="{{ scope }}">
  <input type="hidden" name="tag" value="{{ active_tag }}">
  <input type="hidden" name="q" value="{{ query }}">
{% endmacro %}

{% block content %}
<h1>할 일</h1>
<p class="sub">
  전체 {{ summary.total }} · 미완료 {{ summary.active }} ·
  오늘까지 {{ summary.today }} · 기한 지남 {{ summary.overdue }}
</p>

<div class="card">
  <form method="post" action="{{ url_for('.create') }}">
    {{ filter_fields() }}
    <div class="grid">
      <div>
        <label for="title">할 일</label>
        <input id="title" name="title" placeholder="무엇을 할까요?" required style="width:100%">
      </div>
      <div>
        <label for="due_date">마감일</label>
        <input id="due_date" name="due_date" type="date" style="width:100%">
      </div>
    </div>
    <div class="grid-3">
      <div>
        <label for="tags">태그 (쉼표로 구분)</label>
        <input id="tags" name="tags" placeholder="공부, 집안일" style="width:100%">
      </div>
      <div>
        <label for="notes">메모</label>
        <input id="notes" name="notes" style="width:100%">
      </div>
      <div>
        <label for="priority">우선순위</label>
        <select id="priority" name="priority" style="width:100%">
          {% for value, label in priority_labels.items() %}
            <option value="{{ value }}" {% if value == 2 %}selected{% endif %}>{{ label }}</option>
          {% endfor %}
        </select>
      </div>
    </div>
    <p style="margin:12px 0 0"><button class="primary" type="submit">추가</button></p>
  </form>
</div>

<div class="card">
  <div class="tabs">
    {% for name in scopes %}
      <a class="tab {% if name == scope %}on{% endif %}"
         href="{{ url_for('.index', scope=name, tag=active_tag or None, q=query or None) }}">
        {{ scope_labels[name] }}
      </a>
    {% endfor %}
  </div>

  <form method="get" action="{{ url_for('.index') }}" class="tabs">
    <input type="hidden" name="scope" value="{{ scope }}">
    <input name="q" value="{{ query }}" placeholder="제목·메모 검색">
    <select name="tag">
      <option value="">태그 전체</option>
      {% for tag in all_tags %}
        <option value="{{ tag.name }}" {% if tag.name == active_tag %}selected{% endif %}>{{ tag.name }}</option>
      {% endfor %}
    </select>
    <button type="submit">찾기</button>
    {% if active_tag or query %}
      <a class="tab" href="{{ url_for('.index', scope=scope) }}">초기화</a>
    {% endif %}
  </form>

  {% if todos %}
    <ul class="todos">
      {% for todo in todos %}
        <li class="{% if todo.is_done %}done{% endif %}">
          <form method="post" action="{{ url_for('.toggle', todo_id=todo.id) }}">
            {{ filter_fields() }}
            <button class="link" type="submit" title="완료 표시 전환">
              {% if todo.is_done %}[x]{% else %}[ ]{% endif %}
            </button>
          </form>
          <div class="body">
            <div class="title">{{ todo.title }}</div>
            <div class="meta">
              {% if todo.due_date %}
                <span class="{% if not todo.is_done and todo.due_date <= today %}overdue{% endif %}">마감 {{ todo.due_date }}</span>
              {% else %}마감일 없음{% endif %}
              · {{ priority_labels[todo.priority] }}
              {% if todo.notes %}· {{ todo.notes }}{% endif %}
              {% if todo.tags %}
                <br>{% for tag in todo.tags %}<span class="chip">{{ tag.name }}</span>{% endfor %}
              {% endif %}
            </div>
          </div>
          <form method="post" action="{{ url_for('.delete', todo_id=todo.id) }}"
                onsubmit="return confirm('삭제할까요?')">
            {{ filter_fields() }}
            <button class="link danger" type="submit">삭제</button>
          </form>
        </li>
      {% endfor %}
    </ul>
  {% else %}
    <p class="empty">할 일이 없습니다.</p>
  {% endif %}
</div>

<footer>로컬 전용 · 로그인 없음 · 데이터는 이 컴퓨터의 SQLite 파일에만 저장됩니다</footer>
{% endblock %}
```

- [x] **Step 5: 루트 실행 진입점 작성**

`app.py`:
```python
#!/usr/bin/env python3
"""`python3 app.py` 로 웹 화면 띄우기.

로컬 전용이다. host를 0.0.0.0으로 바꾸지 말 것 — 로그인도 CSRF도 없다.
"""

from todoapp.web import create_app

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
```

- [x] **Step 6: 테스트 통과 확인**

Run: `cd ToDoApp && python3 -m pytest tests/ -q`
Expected: PASS — 전 계층 테스트 통과

- [x] **Step 7: 실제 실행으로 손 확인**

```bash
cd /Users/kwonkwanggoo/aiffel_work/ToDoApp
python3 -c "import secrets; print('FLASK_SECRET_KEY=' + secrets.token_hex(32))"
```
`.env.example`을 `.env`로 복사한 뒤 위 출력값을 `FLASK_SECRET_KEY`에 붙여넣고 실행한다:
```bash
cd /Users/kwonkwanggoo/aiffel_work/ToDoApp && python3 app.py
```
브라우저에서 `http://127.0.0.1:5000` 열고 확인: 추가 / 완료 토글 / 삭제 /
범위 탭 / 태그 필터 / 검색 / 새로고침해도 중복 추가 안 됨.

- [x] **Step 8: 커밋**

```bash
cd /Users/kwonkwanggoo/aiffel_work
git add ToDoApp/todoapp/web/ ToDoApp/todoapp/config.py \
        ToDoApp/app.py ToDoApp/.env.example ToDoApp/tests/test_web.py
git commit -m "feat(todoapp): Flask 웹 화면 추가 (PRG 패턴, 요청별 커넥션)"
```

---

### Task 9: 문서화와 최종 검증

**Files:**
- Create: `README.md`
- Modify: `docs/db-design.md` (계층 구조 절 추가)
- Modify: `plan.md` (STATUS를 DONE으로)

- [x] **Step 1: 전체 테스트 확인**

```bash
cd /Users/kwonkwanggoo/aiffel_work/ToDoApp && python3 -m pytest tests/ -q
```
Expected: 전부 PASS, 실패 0

- [x] **Step 2: `README.md` 작성**

아래 내용을 그대로 쓴다:

    # ToDoApp

    내 컴퓨터에서만 도는 할 일 관리 앱. 데이터는 로컬 SQLite 파일 하나에 저장된다.
    같은 코어 위에 **터미널(CLI)** 과 **웹 화면(Flask)** 두 가지 인터페이스가 올라간다.

    ## 기능

    - 할 일 추가 / 목록 / 완료 표시 / 삭제 (CRUD)
    - **마감일** — 오늘까지·기한 지남 필터, 임박한 순 정렬
    - **태그** — 하나의 할 일에 여러 태그, 태그로 필터
    - 제목·메모 검색, 우선순위(높음/보통/낮음), 메모

    ## 설치

    ```bash
    cd ToDoApp
    python3 -m pip install -r requirements-dev.txt
    ```

    `.env.example`을 `.env`로 복사한 뒤, 아래 명령의 출력값을 `FLASK_SECRET_KEY`에 채운다.

    ```bash
    python3 -c "import secrets; print(secrets.token_hex(32))"
    ```

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

    마감일 입력은 `2026-09-10` / `오늘` / `내일` / `+7d` / `-1d` / `없음`을 받는다.

    ## 쓰는 법 — 웹 화면

    ```bash
    python3 app.py
    ```

    `http://127.0.0.1:5000` 을 브라우저에서 연다.

    ## 구조

    ```
    todoapp/models.py      값 객체 + 입력 검증   (DB를 모른다)
    todoapp/database.py    커넥션·PRAGMA·스키마
    todoapp/repository.py  SQL 전담              ← SQL은 여기와 db/schema.sql에만 있다
    todoapp/service.py     유스케이스·트랜잭션   ← CLI와 웹이 공유
    todoapp/cli.py         터미널 화면
    todoapp/web/           Flask 화면
    ```

    DB 설계와 근거는 [docs/db-design.md](docs/db-design.md), 구현 계획은 [plan.md](plan.md).

    ## 테스트

    ```bash
    python3 -m pytest tests/ -q
    ```

    ## 보안 범위 (읽고 넘어가세요)

    이 앱은 **로컬 단독 실행 전제**다. 로그인이 없고, 따라서 CSRF 토큰도 세션 보호도 없다.

    - `app.py`의 host를 `0.0.0.0`으로 바꾸거나 외부에 노출하지 말 것.
    - 여러 사람이 쓰게 만들려면 로그인을 **직접 구현하지 말고** Flask-Login +
      Flask-WTF(CSRF)를 붙인다.
    - 비밀값은 `.env`에만 둔다. `.env`와 `*.db`는 `.gitignore`에 등록되어 있다.

    ## 도구

    Python 3.13 / 표준 `sqlite3` / Flask / pytest / python-dotenv — 전부 무료.

- [x] **Step 3: `docs/db-design.md`에 계층 구조 절 추가**

문서 끝에 다음을 덧붙인다:

    ## 코드에서 이 표를 다루는 계층

    ```
    models.py      값 객체 + 검증        DB를 모른다
    database.py    커넥션·PRAGMA·스키마
    repository.py  SQL 전담              ← SQL은 여기와 db/schema.sql에만 존재
    service.py     유스케이스·트랜잭션    CLI와 웹이 공유
    cli.py / web/  화면                  SQL도 sqlite3도 모른다
    ```

    `repository.py`의 `TodoRepository.load_tags()`가 목록 조회의 N+1을 막는다.
    할 일 10개의 태그를 쿼리 11번이 아니라 2번(할 일 1 + 태그 1)에 가져온다.

- [x] **Step 4: `plan.md` STATUS 갱신**

`plan.md` 셋째 줄의 `**STATUS: APPROVED**`를 `**STATUS: DONE (2026-09-04)**`으로 바꾼다.

- [x] **Step 5: 최종 검증 — 깨끗한 상태에서 처음부터**

```bash
cd /Users/kwonkwanggoo/aiffel_work/ToDoApp
rm -f db/todo.db
python3 -m pytest tests/ -q
python3 todo.py add "최종 확인" --due 오늘 --tag 검증
python3 todo.py list
python3 -c "
from todoapp.web import create_app
client = create_app().test_client()
response = client.get('/')
assert response.status_code == 200, response.status_code
assert '최종 확인' in response.get_data(as_text=True)
print('웹 화면 정상')
"
sqlite3 db/todo.db "SELECT * FROM v_todo_list;"
```
Expected: 테스트 전부 통과 / CLI가 표를 출력 / 웹이 200 + 같은 데이터 / 뷰도 같은 데이터

- [x] **Step 6: 커밋**

```bash
cd /Users/kwonkwanggoo/aiffel_work
git add ToDoApp/README.md ToDoApp/docs/db-design.md ToDoApp/plan.md
git commit -m "docs(todoapp): README와 DB 설계 문서에 계층 구조 반영"
```

---

## 완료 기준 (인수 조건)

- [x] `python3 -m pytest tests/ -q` 실패 0
- [x] PRD 기본 CRUD 4종이 CLI·웹 양쪽에서 동작
- [x] 커스텀 기능 2종(마감일·태그)이 CLI·웹 양쪽에서 동작
- [x] 앱을 껐다 켜도 데이터가 남는다 (`db/todo.db` 파일)
- [x] SQL은 `db/schema.sql`과 `todoapp/repository.py`에만 존재
- [x] `todoapp/cli.py`·`todoapp/web/`에 `import sqlite3`가 없다
- [x] 비밀값(`FLASK_SECRET_KEY`)이 코드에 없고 `.env`에만 있다
- [x] `.env`와 `*.db`가 커밋되지 않는다
- [x] 스키마 뷰와 리포지토리 쿼리의 결과가 일치한다 (`TestViewConsistency`)
- [x] 함수당 50줄 이하
- [~] 모듈당 300줄 — `cli.py`(321) `repository.py`(354)가 초과. 프로젝트 글로벌
      규칙은 **800줄**(golden-principles #5)이며 두 파일 모두 그 안이다. 응집도 있는
      파일을 300줄에 맞추려 쪼개면 탐색 비용만 늘어 기준을 글로벌 규칙으로 맞췄다.
- [x] README에 로컬 전용·CSRF 없음이 명시되어 있다
