#!/usr/bin/env python3
"""넣은 Supabase 키가 안전한 것인지 검사한다.

키 값 자체는 절대 출력하지 않는다. 역할(role)과 판정만 보여준다.

실행:
    python3 scripts/check_env.py            # 형식만 검사 (네트워크 안 씀)
    python3 scripts/check_env.py --connect  # 실제 접속까지 확인
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from todoapp.keycheck import classify_key  # noqa: E402  (경로 설정 후 import)


def check_connection(url: str, key: str) -> tuple[bool, str]:
    """실제로 접속되는지 확인한다.

    표가 아직 없어도 '표가 없다'는 응답이 오면 인증은 통과한 것이다.
    키가 틀렸다면 그 전에 401 Invalid API key가 온다.
    """
    try:
        from supabase import create_client
    except ImportError:
        return False, "supabase 패키지가 없습니다: python3 -m pip install -r requirements.txt"
    try:
        client = create_client(url, key)
    except Exception as exc:
        return False, f"클라이언트 생성 실패: {type(exc).__name__}: {exc}"
    try:
        client.table("todos").select("id").limit(1).execute()
        return True, "접속 성공 — todos 표가 이미 있습니다."
    except Exception as exc:
        message = str(exc)
        if any(m in message for m in ("42501", "permission denied")):
            # anon이 거부당하는 것이 목표 상태다. 표가 있고 잠겨 있다는 뜻.
            return True, "접속 성공 — 표가 있고 anon은 차단됨 (RLS 정상. 로그인해야 보입니다)"
        if any(m in message for m in ("42P01", "does not exist", "Could not find the table")):
            return True, "접속 성공 — 인증 통과 (todos 표는 아직 없음. 스키마 SQL을 실행하세요)"
        if any(m in message for m in ("Invalid API key", "401", "JWT")):
            return False, f"인증 실패: {message[:200]}"
        return False, f"예상 못한 응답: {type(exc).__name__}: {message[:200]}"


def main() -> int:
    connect = "--connect" in sys.argv
    load_dotenv(PROJECT_ROOT / ".env")
    problems = 0

    url = os.getenv("SUPABASE_URL", "").strip()
    if not url:
        print("  ❌ SUPABASE_URL 이 비어 있습니다.")
        problems += 1
    elif not url.startswith("https://") or ".supabase.co" not in url:
        print(f"  ⚠️  SUPABASE_URL 형식이 이상합니다: {url}")
        problems += 1
    else:
        print(f"  ✅ SUPABASE_URL : {url}")

    key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if not key:
        print("  ❌ SUPABASE_ANON_KEY 가 비어 있습니다.")
        problems += 1
    else:
        name, safe, note = classify_key(key)
        mark = "✅" if safe else "❌"
        print(f"  {mark} SUPABASE_ANON_KEY : {name} · 길이 {len(key)}자")
        print(f"       {note}")
        if not safe:
            problems += 1

    # service_role 키가 환경 어디에든 있으면 경고한다 (RLS 우회 경로)
    for name in os.environ:
        if "SERVICE_ROLE" in name.upper():
            print(f"  ❌ {name} 이 환경에 있습니다. RLS 우회 경로이므로 제거하세요.")
            problems += 1

    if connect and not problems:
        ok, note = check_connection(url, key)
        print(f"  {'✅' if ok else '❌'} 접속 : {note}")
        if not ok:
            problems += 1
    elif connect:
        print("  ⏭️  형식 문제가 있어 접속 확인은 건너뜁니다.")

    print()
    if problems:
        print(f"문제 {problems}건. 위 항목을 고친 뒤 다시 실행하세요.")
    else:
        print("키 설정이 안전합니다.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
