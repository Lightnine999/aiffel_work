# Supabase 이행 계획

**STATUS: DRAFT** ← 승인 시 `APPROVED`로 변경. 승인 전 구현 착수 금지.

**목표:** 같은 Todo 앱을 Supabase(무료 클라우드 Postgres)에도 저장할 수 있게 한다.
접속 키는 `.env`로만, RLS로 "내 행만" 강제. SQLite 경로는 남기고 `.env`로 전환한다.

**확정된 결정 (2026-09-04 사용자 승인)**
- 인증: Supabase Auth 이메일+비밀번호. RLS는 `user_id = auth.uid()`
- 범위: 웹·CLI 둘 다 로그인
- SQLite: 남기고 `STORAGE=sqlite|supabase`로 전환
- Supabase 프로젝트: 보유 중. 키는 사용자가 `.env`에 직접 입력

**실측 확인된 API (2026-09-04, supabase 2.31.0 설치 후 introspection)**
- `create_client(url, key, options)` / `client.table(...)` / `client.rpc(fn, params)`
- `client.auth.sign_in_with_password({"email":…, "password":…})` → `AuthResponse`
- `client.auth.sign_up(...)` / `sign_out()` / `set_session(access_token, refresh_token)`
- `client.auth.refresh_session(refresh_token)` / `get_user(jwt=None)` / `get_session()`
- 쿼리 빌더: `select insert update upsert delete` + `eq neq lt lte gt gte is_ in_ ilike or_ not_ order limit single maybe_single`

---

## 전역 제약 (CRITICAL)

1. **`service_role` 키를 앱 어디에도 두지 않는다.** anon key만 쓴다.
   `service_role`은 RLS를 우회하므로, 두는 순간 RLS가 방어선이 아니라 장식이 된다.
   `.env.example`에도 넣지 않는다.
2. **키는 `.env`에서만 읽고 미설정 시 throw.** 기본값 금지.
3. **`security definer` 함수 금지.** RPC는 전부 `security invoker` — RLS를 통과해야 한다.
4. **`models`·`service` 위쪽(cli·web)은 Supabase를 모른다.** 저장소 교체가 화면에 새면
   이음새를 잘못 그은 것이다.
5. 기존 SQLite 테스트 254개는 **네트워크 없이 계속 통과**해야 한다.
6. 언어: 주석·문서·커밋 한국어. 모듈 800줄 / 함수 50줄 이하.

## 계약 변경 2건 (중요)

| 항목 | SQLite (기존) | Supabase (신규) | 왜 |
|---|---|---|---|
| 태그 유일성 | `name` **전역** UNIQUE | `(user_id, name)` UNIQUE | 전역이면 남이 만든 "공부"와 충돌한다 |
| 원자성 | `with conn:` 트랜잭션 | **RPC 함수** | PostgREST에는 클라이언트 트랜잭션이 없다 |

**원자성이 핵심 함정이다.** "할 일 추가 + 태그 3개 연결"은 REST로 3~4번의 왕복이라
중간에 실패하면 반쯤 만들어진 상태가 남는다. Postgres 함수로 서버에서 한 번에 처리한다.

## 파일 구조

| 파일 | 상태 | 책임 |
|---|---|---|
| `todoapp/models.py` | **그대로** | 값 객체·검증 |
| `todoapp/service.py` | 수정 | `conn` 대신 `Store`를 받는다 |
| `todoapp/cli.py`, `web/` | 수정 | 로그인 명령·화면 추가. 저장소는 모른다 |
| `todoapp/stores/__init__.py` | 신규 | `Store` 프로토콜 + `build_store()` 팩토리 |
| `todoapp/stores/sqlite_store.py` | 신규 | 기존 `repository.py`를 감싼다 |
| `todoapp/stores/supabase_store.py` | 신규 | supabase-py 구현 |
| `todoapp/supabase_client.py` | 신규 | 클라이언트 생성 + 세션 주입 |
| `todoapp/session.py` | 신규 | CLI 토큰 저장소 (`~/.config/todoapp/session.json`, 0600) |
| `db/supabase_schema.sql` | 신규 | 스키마 + RLS + 트리거 + RPC |
| `db/schema.sql`, `repository.py`, `database.py` | **그대로** | SQLite 경로 |

---

## Task 1 — Store 이음새 도입 (SQLite 쪽만, 동작 변화 0)

`TodoService(conn)` → `TodoService(store)`. 기존 254개가 계속 통과해야 한다.

- [ ] `Store` 프로토콜 정의: `.todos` / `.tags` / `.transaction()` 컨텍스트매니저
- [ ] `SqliteStore(conn)` 작성 — `.transaction()` = `with conn:`
- [ ] `service.py`의 `with self._conn:` 를 `with self._store.transaction():` 로 교체
- [ ] `TodoService(conn)`도 계속 받게 한다 (conn이면 `SqliteStore`로 감싼다) — 기존 테스트 무수정
- [ ] `tests/test_stores.py`: `SqliteStore`가 프로토콜을 만족하는지, `transaction()` 롤백 확인
- [ ] `python3 -m pytest tests/ -q` → 254개 + 신규 통과
- [ ] 커밋

## Task 2 — Postgres 마이그레이션 SQL

사용자가 Supabase 대시보드 > SQL Editor에 붙여 실행한다. `db/supabase_schema.sql` 전문:

```sql
-- ToDoApp Supabase 스키마 + RLS. 대시보드 > SQL Editor에 붙여 실행.
create extension if not exists citext;

create table if not exists public.todos (
    id           bigserial primary key,
    user_id      uuid not null default auth.uid()
                 references auth.users(id) on delete cascade,
    title        text not null
                 check (length(btrim(title)) between 1 and 200),
    notes        text,
    is_done      boolean not null default false,
    due_date     date,
    priority     smallint not null default 2 check (priority in (1,2,3)),
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    completed_at timestamptz
);

-- 태그 유일성은 '사용자별'이다. 전역 UNIQUE면 남의 태그와 충돌한다.
-- citext라 비교가 대소문자를 무시한다 (SQLite의 COLLATE NOCASE와 같은 효과).
create table if not exists public.tags (
    id         bigserial primary key,
    user_id    uuid not null default auth.uid()
               references auth.users(id) on delete cascade,
    name       citext not null
               check (length(btrim(name::text)) between 1 and 30
                      and position(',' in name::text) = 0),
    color      text not null default '#888880'
               check (color ~ '^#[0-9A-Fa-f]{6}$'),
    created_at timestamptz not null default now(),
    unique (user_id, name)
);

create table if not exists public.todo_tags (
    todo_id bigint not null references public.todos(id) on delete cascade,
    tag_id  bigint not null references public.tags(id)  on delete cascade,
    primary key (todo_id, tag_id)
);

create index if not exists idx_todos_user_due  on public.todos(user_id, due_date);
create index if not exists idx_todos_user_done on public.todos(user_id, is_done);
create index if not exists idx_todo_tags_tag   on public.todo_tags(tag_id);

-- 트리거: BEFORE에서 NEW를 고친다. SQLite처럼 AFTER + 재귀 UPDATE가 필요 없다.
create or replace function public.touch_updated_at() returns trigger
language plpgsql as $$
begin
    new.updated_at := now();
    return new;
end $$;

create or replace function public.sync_completed_at() returns trigger
language plpgsql as $$
begin
    if new.is_done and not old.is_done then
        new.completed_at := now();
    elsif not new.is_done then
        new.completed_at := null;
    end if;
    return new;
end $$;

drop trigger if exists trg_todos_touch on public.todos;
create trigger trg_todos_touch before update on public.todos
    for each row execute function public.touch_updated_at();

drop trigger if exists trg_todos_completed on public.todos;
create trigger trg_todos_completed before update of is_done on public.todos
    for each row execute function public.sync_completed_at();

-- ============ 권한: 2층 구조 ============
-- 1층 GRANT로 '표에 손댈 수 있는 역할'을 정하고, 2층 RLS로 '어느 행'인지 정한다.
-- anon(공개 키로 접근하는 역할)에게는 아무 권한도 주지 않는다.
grant usage on schema public to anon, authenticated;
grant all on public.todos, public.tags, public.todo_tags to authenticated;
grant usage, select on all sequences in schema public to authenticated;
revoke all on public.todos, public.tags, public.todo_tags from anon;

-- ============ RLS ============
alter table public.todos     enable row level security;
alter table public.tags      enable row level security;
alter table public.todo_tags enable row level security;

drop policy if exists todos_own on public.todos;
create policy todos_own on public.todos
    for all to authenticated
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

drop policy if exists tags_own on public.tags;
create policy tags_own on public.tags
    for all to authenticated
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

-- todo_tags에는 user_id가 없다. 부모 행의 소유자로 판정한다.
-- with check에서 태그 쪽도 확인한다 — 안 하면 내 할 일에 남의 태그를 붙일 수 있다.
drop policy if exists todo_tags_own on public.todo_tags;
create policy todo_tags_own on public.todo_tags
    for all to authenticated
    using (exists (select 1 from public.todos t
                    where t.id = todo_id and t.user_id = auth.uid()))
    with check (exists (select 1 from public.todos t
                         where t.id = todo_id and t.user_id = auth.uid())
            and exists (select 1 from public.tags g
                         where g.id = tag_id and g.user_id = auth.uid()));

-- ============ RPC: 원자성 ============
-- PostgREST에는 클라이언트 트랜잭션이 없다. 여러 문장이 한 덩어리여야 하는 작업은
-- 함수로 만들어 서버에서 처리한다.
-- security invoker(기본값)를 명시한다 — definer로 만들면 RLS를 우회한다.

create or replace function public.upsert_tags(p_names text[])
returns bigint[]
language plpgsql security invoker set search_path = public
as $$
declare
    result bigint[] := '{}';
    nm text;
    tid bigint;
begin
    foreach nm in array coalesce(p_names, '{}'::text[]) loop
        nm := btrim(nm);
        continue when nm = '';
        -- 이미 있으면 색상을 그대로 다시 써서(무변경) id만 돌려받는다.
        -- name = excluded.name 으로 쓰면 먼저 저장된 표기가 덮여 쓰인다.
        insert into public.tags (name) values (nm)
        on conflict (user_id, name) do update set color = tags.color
        returning id into tid;
        result := result || tid;
    end loop;
    return result;
end $$;

create or replace function public.create_todo_with_tags(
    p_title    text,
    p_notes    text     default null,
    p_due_date date     default null,
    p_priority smallint default 2,
    p_tags     text[]   default '{}'
) returns bigint
language plpgsql security invoker set search_path = public
as $$
declare
    new_id  bigint;
    tag_ids bigint[];
begin
    insert into public.todos (title, notes, due_date, priority)
    values (btrim(p_title),
            nullif(btrim(coalesce(p_notes, '')), ''),
            p_due_date, p_priority)
    returning id into new_id;

    tag_ids := public.upsert_tags(p_tags);
    if array_length(tag_ids, 1) is not null then
        insert into public.todo_tags (todo_id, tag_id)
        select new_id, unnest(tag_ids)
        on conflict do nothing;
    end if;
    return new_id;
end $$;

create or replace function public.set_todo_tags(p_todo_id bigint, p_tags text[])
returns void
language plpgsql security invoker set search_path = public
as $$
declare tag_ids bigint[];
begin
    -- 소유권 검사를 따로 하지 않는다. RLS가 남의 행을 애초에 보이지 않게 하므로
    -- 남의 todo_id를 넘겨도 delete가 0건, insert가 정책 위반으로 실패한다.
    delete from public.todo_tags where todo_id = p_todo_id;
    tag_ids := public.upsert_tags(p_tags);
    if array_length(tag_ids, 1) is not null then
        insert into public.todo_tags (todo_id, tag_id)
        select p_todo_id, unnest(tag_ids)
        on conflict do nothing;
    end if;
end $$;

revoke all on function public.upsert_tags(text[])            from anon;
revoke all on function public.create_todo_with_tags(text, text, date, smallint, text[]) from anon;
revoke all on function public.set_todo_tags(bigint, text[])  from anon;
grant execute on function public.upsert_tags(text[])            to authenticated;
grant execute on function public.create_todo_with_tags(text, text, date, smallint, text[]) to authenticated;
grant execute on function public.set_todo_tags(bigint, text[])  to authenticated;
```

- [ ] 위 SQL을 `db/supabase_schema.sql`로 저장
- [ ] `docs/supabase-setup.md`에 적용 절차 작성 (프로젝트 설정 → 키 위치 → SQL 실행 → 이메일 확인 옵션)
- [ ] **사용자가 대시보드에서 실행**하고 완료를 알려준다
- [ ] 커밋

## Task 3 — 설정·인증·세션

- [ ] `config.py`: `get_storage_backend()` (`sqlite`|`supabase`), `get_supabase_url()`, `get_supabase_anon_key()` — 전부 미설정 시 throw
- [ ] `config.py`에 가드 추가: `SUPABASE_SERVICE_ROLE_KEY`가 환경에 있으면 **즉시 예외**.
      실수로 넣어두면 RLS 우회 경로가 생기므로 코드가 거부한다
- [ ] `supabase_client.py`: `build_client()`, `sign_in(email, pw)`, `sign_up`, `attach_session(client, tokens)`
- [ ] `session.py`: `save(tokens)` / `load()` / `clear()`. 파일 `~/.config/todoapp/session.json`,
      `os.open(..., 0o600)`으로 생성. 부모 디렉터리도 0700
- [ ] `.env.example` 갱신 (`STORAGE`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`. service_role은 넣지 않음)
- [ ] 테스트: 키 미설정 시 throw / service_role 감지 시 throw / 세션 파일 권한이 0600 / 토큰 왕복
- [ ] 커밋

## Task 4 — SupabaseStore

- [ ] `SupabaseTagRepository`: `upsert`(→ `rpc('upsert_tags')`), `get`, `get_by_name`, `list_all`
- [ ] `SupabaseTodoRepository`: `add`(→ `rpc('create_todo_with_tags')`), `get`, `list`, `update`,
      `set_done`, `delete`, `replace_tags`(→ `rpc('set_todo_tags')`), `load_tags`
- [ ] `list()`의 필터를 PostgREST로 옮긴다: `eq/lte/lt/is_/or_/order`.
      키워드 검색은 `or_("title.ilike.*kw*,notes.ilike.*kw*")` — **`*`가 PostgREST의
      와일드카드이므로 사용자 입력의 `*`와 `,`를 이스케이프해야 한다** (SQLite의 `%`와 같은 함정)
- [ ] 태그 필터: `todo_tags!inner(tags!inner(name))` 임베드 또는 2단 조회. 중복 행 방지 확인
- [ ] `SupabaseStore.transaction()`은 no-op 컨텍스트매니저 + 왜 그런지 주석
- [ ] 테스트: 가짜 클라이언트(호출 기록용)로 "어떤 요청을 만드는지" 검증. 네트워크 불필요
- [ ] 커밋

## Task 5 — CLI·웹 로그인

- [ ] CLI: `todo login` / `todo logout` / `todo whoami`. 비밀번호는 `getpass`로 받고 화면에 안 찍는다
- [ ] CLI: `STORAGE=supabase`인데 세션이 없으면 `todo login` 안내와 함께 종료 코드 1
- [ ] 웹: `GET/POST /login`, `POST /logout`, `GET/POST /signup`. Flask session에 토큰 보관
- [ ] 웹: 미로그인 시 `/`가 `/login`으로 리다이렉트 (`before_request` 가드)
- [ ] 만료 토큰 처리: `refresh_session` 1회 시도 → 실패 시 세션 비우고 재로그인 요구
- [ ] 테스트: 미로그인 리다이렉트 / 로그인·로그아웃 흐름 / 만료 토큰 갱신 (가짜 클라이언트)
- [ ] 커밋

## Task 6 — 실연결 검증 + RLS 격리 증명 + 문서

- [ ] `tests/test_supabase_integration.py` — `SUPABASE_URL`이 없으면 `pytest.mark.skip`.
      실제 프로젝트 대상 CRUD·마감일·태그 왕복
- [ ] **RLS 격리 테스트 (이 작업의 핵심 증거)**: 계정 A로 할 일 생성 → 계정 B로 로그인 →
      A의 행이 `list()`에 안 보이고, A의 id를 직접 지정한 `update`/`delete`가 0건임을 확인
- [ ] **anon key 단독 접근 테스트**: 로그인 없이 anon key만으로 `todos`를 읽으면 0건/거부
- [ ] `README.md`에 Supabase 전환법·로그인·보안 모델 추가. CSRF 문단 갱신
      (로그인이 생겼으므로 이제 CSRF가 실제 위험 — Flask-WTF 도입 여부를 명시적으로 남긴다)
- [ ] `python3 -m pytest tests/ -q` 전체 통과
- [ ] 커밋

---

## 완료 기준

- [ ] `STORAGE=sqlite`에서 기존 254개 테스트가 네트워크 없이 통과
- [ ] `STORAGE=supabase`에서 CRUD·마감일·태그가 CLI·웹 양쪽에서 동작
- [ ] **계정 B가 계정 A의 행을 읽지도 고치지도 지우지도 못함 (테스트로 증명)**
- [ ] **anon key만으로는 아무 행도 못 읽음 (테스트로 증명)**
- [ ] `service_role` 문자열이 코드·`.env.example`에 없고, 환경에 있으면 앱이 거부
- [ ] `SUPABASE_*` 키가 코드에 없고 `.env`에만 있음
- [ ] 세션 파일 권한이 0600
- [ ] `cli.py`·`web/`에 `supabase` import가 없음 (저장소 무지 유지)
- [ ] RPC 3개가 모두 `security invoker`
- [ ] 모듈 800줄 / 함수 50줄 이하

## 남은 위험

| 위험 | 대응 |
|---|---|
| Supabase 무료 플랜은 **1주 비활성 시 프로젝트 일시정지** | README에 명시. 정지되면 대시보드에서 재개 |
| 이메일 확인(Confirm email)이 기본 켜져 있어 `sign_up` 직후 로그인 실패 가능 | `docs/supabase-setup.md`에 끄는 방법 안내 (학습용 프로젝트 전제) |
| 로그인이 생겨 CSRF가 실제 위험이 됨 | Task 6에서 명시적으로 판단해 문서에 남긴다. 붙일 경우 Flask-WTF |
| 통합 테스트가 실제 프로젝트에 데이터를 남김 | 테스트마다 고유 접두사 + 종료 시 정리 |
