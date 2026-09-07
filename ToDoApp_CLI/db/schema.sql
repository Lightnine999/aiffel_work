-- ToDoApp SQLite 스키마
-- 실행: sqlite3 db/todo.db < db/schema.sql

-- SQLite는 외래키 검사가 기본 OFF다. 연결할 때마다 켜야 한다.
PRAGMA foreign_keys = ON;

-- 1) 할 일
CREATE TABLE IF NOT EXISTS todos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL CHECK (length(trim(title)) > 0),
    notes        TEXT,
    is_done      INTEGER NOT NULL DEFAULT 0 CHECK (is_done IN (0, 1)),
    -- 'YYYY-MM-DD' 형태이면서 실제로 존재하는 날짜만 허용
    -- (GLOB은 '_'를 와일드카드로 안 쓴다. date()로 왕복 비교하는 편이 정확하다)
    due_date     TEXT             CHECK (due_date IS NULL OR
                                        (date(due_date) IS NOT NULL AND due_date = date(due_date))),
    priority     INTEGER NOT NULL DEFAULT 2 CHECK (priority IN (1, 2, 3)),
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    completed_at TEXT
);

-- 2) 태그
CREATE TABLE IF NOT EXISTS tags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    color      TEXT    NOT NULL DEFAULT '#888880',
    created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 3) 할 일 <-> 태그 연결 (N:M)
CREATE TABLE IF NOT EXISTS todo_tags (
    todo_id INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (todo_id, tag_id)
);

-- 인덱스: 자주 거르는 열에만
CREATE INDEX IF NOT EXISTS idx_todos_due_date  ON todos(due_date);
CREATE INDEX IF NOT EXISTS idx_todos_is_done   ON todos(is_done);
CREATE INDEX IF NOT EXISTS idx_todo_tags_tag   ON todo_tags(tag_id);

-- 트리거: 수정 시 updated_at 자동 갱신
CREATE TRIGGER IF NOT EXISTS trg_todos_updated_at
AFTER UPDATE ON todos
FOR EACH ROW
BEGIN
    UPDATE todos SET updated_at = datetime('now', 'localtime') WHERE id = OLD.id;
END;

-- 트리거: 완료 표시하면 completed_at 기록, 되돌리면 지움
CREATE TRIGGER IF NOT EXISTS trg_todos_completed_at
AFTER UPDATE OF is_done ON todos
FOR EACH ROW
BEGIN
    UPDATE todos
       SET completed_at = CASE WHEN NEW.is_done = 1
                               THEN datetime('now', 'localtime')
                               ELSE NULL END
     WHERE id = OLD.id;
END;

-- 아래 뷰 2개는 `sqlite3 db/todo.db` 로 DB를 직접 들여다볼 때 쓰는 점검용이다.
-- 앱 코드는 이 뷰를 쓰지 않고 repository.py의 파라미터화된 쿼리를 쓴다
-- (테스트에서 날짜를 고정할 수 있어야 하므로). 두 경로가 갈라지지 않도록
-- tests/test_repository_list.py::TestViewConsistency가 결과 일치를 검사한다.

-- 뷰: 오늘 할 일 (마감일이 오늘이거나 이미 지난 미완료 항목)
CREATE VIEW IF NOT EXISTS v_today_todos AS
SELECT t.*
  FROM todos t
 WHERE t.is_done = 0
   AND t.due_date IS NOT NULL
   AND t.due_date <= date('now', 'localtime')
 ORDER BY t.due_date ASC, t.priority ASC, t.id ASC;

-- 뷰: 목록 화면용 (태그를 한 줄로 합쳐서 조회)
CREATE VIEW IF NOT EXISTS v_todo_list AS
SELECT t.id,
       t.title,
       t.is_done,
       t.due_date,
       t.priority,
       GROUP_CONCAT(g.name, ', ') AS tag_names
  FROM todos t
  LEFT JOIN todo_tags tt ON tt.todo_id = t.id
  LEFT JOIN tags g       ON g.id = tt.tag_id
 GROUP BY t.id
 ORDER BY t.is_done ASC, t.due_date IS NULL ASC, t.due_date ASC,
          t.priority ASC, t.id ASC;
