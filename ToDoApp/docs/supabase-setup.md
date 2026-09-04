# Supabase 설정 절차

이 문서는 `db/supabase_schema.sql`을 적용하고 앱을 클라우드로 전환하는 절차다.

프로젝트 정보 (2026-09-04 확인)

| 항목 | 값 |
|---|---|
| 프로젝트 | Lightnine999's Project |
| 리전 | Northeast Asia (Seoul) · ap-northeast-2 |
| Project URL | `https://zocsvheggxbtczhdgple.supabase.co` |
| 플랜 | 무료 |

---

## 1. 키 설정 (완료)

`.env`에 다음 세 줄이 있어야 한다. **`SUPABASE_SERVICE_ROLE_KEY`는 넣지 않는다.**

```
STORAGE=sqlite
SUPABASE_URL=https://zocsvheggxbtczhdgple.supabase.co
SUPABASE_ANON_KEY=<anon 또는 publishable 키>
```

키 위치: 대시보드 → 프로젝트 → ⚙️ **Project Settings** → **API Keys**

| 화면에 보이는 것 | 쓰는가 |
|---|---|
| `Publishable key` (`sb_publishable_…`) | ✅ |
| `anon` `public` (`eyJ…`) | ✅ (기존 방식) |
| `Secret keys` / `service_role` | ❌ RLS를 우회한다 |
| **`JWT Secret`** (64자 hex) | ❌ 신원 위조가 가능해 더 위험하다 |

**가려져 있고 Reveal 버튼이 있으면 그건 아니다.** anon 키는 브라우저에 노출되는 게
정상이라 가려두지 않는다.

확인:

```bash
python3 scripts/check_env.py --connect
```

`✅` 세 줄이 나오면 된다. 이 스크립트는 키 값을 출력하지 않고 종류·길이만 보고한다.

## 2. 스키마 적용

대시보드 → 좌측 **SQL Editor** → **New query** → `db/supabase_schema.sql` 전체를
붙여넣고 **Run**.

여러 번 실행해도 안전하다 (`if not exists` / `or replace`).

적용되는 것:

| 종류 | 이름 |
|---|---|
| 표 3 | `todos` `tags` `todo_tags` |
| 인덱스 3 | `idx_todos_user_due` `idx_todos_user_done` `idx_todo_tags_tag` |
| 트리거 2 | `trg_todos_touch` `trg_todos_completed` |
| RLS 정책 3 | `todos_own` `tags_own` `todo_tags_own` |
| 함수 5 | `touch_updated_at` `sync_completed_at` `upsert_tags` `create_todo_with_tags` `set_todo_tags` |

적용 후 확인:

```bash
python3 scripts/check_env.py --connect
```

`todos 표가 아직 없음` → `todos 표가 이미 있습니다`로 바뀌면 성공이다.

## 3. 이메일 확인 끄기 (학습용 프로젝트 전제)

기본값은 **가입 후 이메일 확인을 해야 로그인**이 된다. 실제 메일함을 열어야 하므로
개발 중에는 번거롭다.

대시보드 → **Authentication** → **Sign In / Providers** → **Email** →
**Confirm email** 끄기

> 실제 서비스로 쓸 거라면 이건 켜둬야 한다. 남의 이메일로 가입하는 것을 막는 장치다.

## 4. 계정 만들기

```bash
python3 todo.py signup      # 또는 웹 화면의 회원가입
python3 todo.py login
```

## 5. 전환

`.env`의 `STORAGE`를 바꾼다.

```
STORAGE=supabase
```

되돌리려면 `sqlite`로 바꾸면 된다. 두 저장소는 서로 독립이라 데이터가 섞이지 않는다.

---

## 보안 모델 — 2층 구조

RLS만으로 지켜지는 게 아니다. 두 층이 함께 막는다.

```
1층  GRANT   "어느 역할이 이 표에 손댈 수 있나"
             authenticated → 가능 / anon → 아무 권한 없음
2층  RLS     "그 역할이 어느 행을 볼 수 있나"
             user_id = auth.uid() 인 행만
```

그래서 **anon 키만 가진 사람은 로그인 없이는 아무 행도 읽지 못한다.** 로그인해도
자기 행만 보인다.

앱이 이 방어를 우회할 방법이 없다는 게 핵심이다. `service_role` 키를 어디에도 두지
않으므로, 앱 코드에 버그가 있어도 남의 행에는 닿지 못한다. `config.py`가
환경에 `SERVICE_ROLE` 이름의 변수가 있으면 앱 시작을 거부한다.

RPC 함수 3개는 모두 `security invoker`다. `security definer`로 만들면 함수가
소유자 권한으로 돌아 RLS를 통과해 버린다.

## 알아둘 것

| 항목 | 내용 |
|---|---|
| **무료 플랜 일시정지** | 1주 동안 활동이 없으면 프로젝트가 멈춘다. 대시보드에서 재개(Restore) 클릭 |
| **태그 유일성 범위 변경** | SQLite는 `name` 전역 UNIQUE였다. Postgres는 `(user_id, name)`이다. 전역이면 남의 태그와 충돌한다 |
| **트랜잭션 없음** | PostgREST에는 클라이언트 트랜잭션이 없다. 원자성이 필요한 작업은 RPC 함수로 처리한다 |
| **CSRF** | 로그인이 생기면서 CSRF가 실제 위험이 됐다. 로컬 단독 실행 전제를 유지하되, 외부 노출 시 Flask-WTF를 붙인다 |
