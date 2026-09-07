-- ============================================================
--  ToDoApp — Supabase(Postgres) 스키마 + RLS
--
--  적용: Supabase 대시보드 > SQL Editor 에 이 파일 전체를 붙여 실행
--  절차 상세: docs/supabase-setup.md
--
--  이 파일은 여러 번 실행해도 안전하다 (if not exists / or replace).
-- ============================================================

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
