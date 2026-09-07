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

## 3-2. 돌아올 주소(URL Configuration) 설정 — 비밀번호 찾기에 필수

재설정 메일의 링크는 Supabase가 검증한 뒤 **Site URL**로 돌려보낸다. 기본값이
`http://localhost:3000`이라 그대로 두면 링크를 눌러도 `ERR_CONNECTION_REFUSED`가 뜬다.

대시보드 → **Authentication** → **URL Configuration**

| 항목 | 값 |
|---|---|
| Site URL | `http://127.0.0.1:5001` |
| Redirect URLs | `http://127.0.0.1:5001/**` · `http://localhost:5001/**` |

(2026-09-07 적용 완료. 옛 `:5000` 항목도 남겨뒀다 — 지워도 무방하다)

> **포트가 5000이 아닌 이유**: macOS Monterey부터 **AirPlay 수신기가 5000번을 상시 점유**한다.
> Flask 기본 포트가 5000이라 무심코 쓰면 앱과 자리를 나눠 갖게 되고,
> `localhost:5000`은 AirPlay가 받아 **403 (Server: AirTunes)** 을 돌려준다.
> 5001로 옮겨 `localhost`·`127.0.0.1` 둘 다 정상 동작한다.
> 포트는 `.env`의 `PORT`로 바꿀 수 있다.

## 3-3. 왜 링크 방식인가 — 6자리 코드를 못 쓰는 이유

무료 플랜은 **커스텀 SMTP 없이 메일 템플릿을 수정할 수 없다.** 대시보드에 이렇게
쓰여 있다:

> Set up custom SMTP to edit templates.
> Emails will be sent using the default templates.

기본 "Reset password" 템플릿에는 **링크만 있고 6자리 코드가 없다.** 코드를 실으려면
템플릿에 `{{ .Token }}`을 넣어야 하는데 그게 막혀 있다. 그래서 링크 방식을 쓴다.

**커스텀 SMTP를 붙이면** (Resend·SendGrid 등 무료 티어 → **Authentication → Emails →
SMTP Settings**) 템플릿 수정이 열리고, 덤으로 **팀원이 아닌 사람에게도 메일이 간다**
(기본 SMTP는 프로젝트 팀원 주소로만 발송하며 시간당 2통 제한이 있다).

## 3-4. 비밀번호 찾기 — 쓰는 법

**웹 (권장)**

1. 로그인 화면 → **"비밀번호를 잊으셨나요?"**
2. 이메일 입력 → 메일함(스팸함 포함)에서 `Reset your password` 열기
3. **Reset password** 링크 클릭 → 앱으로 돌아옴
4. 새 비밀번호 2회 입력 → 끝 (바로 로그인 상태)

**터미널**

```bash
python3 todo.py reset-password --email <가입한 이메일>
```

메일의 링크를 **누르지 말고** 우클릭 → **링크 주소 복사** 해서 붙여넣는다.
링크는 한 번만 쓸 수 있어서, 브라우저에서 누르면 터미널에서는 못 쓴다.

> 링크에 담긴 토큰은 서버가 `verify_otp(token_hash=…)`로 직접 확인한다.
> 웹은 Supabase가 돌려준 세션 토큰을 쓰고(주소의 `#` 뒤에 실려 오므로
> 자바스크립트가 꺼낸다), 터미널은 링크의 토큰을 쓴다. 경로는 둘이지만
> 마지막 단계(`update_user`로 비밀번호 변경)는 같다.

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
