---
name: todo-summary
description: 오늘 완료한 할 일을 커밋 메시지 형식으로 요약할 때 사용. "오늘 완료 요약", "오늘 뭐 했지", "완료 커밋 메시지" 요청에 쓴다.
---

# 오늘 완료 요약

오늘 끝낸 할 일을 뽑아 커밋 메시지 형식으로 정리한다.

## 1. 실행

```bash
cd /Users/kwonkwanggoo/aiffel_work/ToDoApp_CLI && STORAGE=sqlite python3 todo.py summary
```

완료시각까지 필요하면 완료된 ID마다 이어서 실행한다.

```bash
cd /Users/kwonkwanggoo/aiffel_work/ToDoApp_CLI && STORAGE=sqlite python3 todo.py show <ID>
```

> `STORAGE=sqlite`를 붙이는 이유: `.env` 기본값이 `supabase`이고, 그쪽은 로그인이
> 필요하다. 클라우드 데이터를 요약해야 할 때만 `STORAGE` 없이 실행한다
> (로그인은 사용자가 직접 한다).

## 2. 커밋 메시지 형식으로 정리

```
chore(todo): 오늘 할 일 N건 완료

- <제목> (마감 <마감일>, <HH:MM> 완료)
- <제목> (마감 <마감일>, <HH:MM> 완료)

남은 일 N건 · 오늘 마감 N건 · 기한 지남 N건
```

- 제목 줄은 완료 건수만 쓴다. 항목 이름은 본문에 둔다.
- 마감일이 없는 항목은 `(마감 없음, HH:MM 완료)`로 쓴다.
- 완료한 것이 **0건이면** 커밋 메시지를 만들지 않고 "오늘 완료한 일이 없습니다"라고만 답한다.

## 3. 원본 출력도 함께 보여준다

정리한 메시지 아래에 `summary` 명령의 출력을 그대로 붙인다.
사용자가 숫자를 직접 확인할 수 있어야 한다.

## 하지 말 것

- ❌ 완료 건수·시각을 추측해서 쓰지 말 것. 반드시 명령을 실행한 출력만 쓴다.
- ❌ 이 스킬로 실제 `git commit`을 하지 말 것. **메시지 문구만** 만든다.
- ❌ `todo.db`를 수정하지 말 것 (조회 전용).
