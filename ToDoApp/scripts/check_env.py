#!/usr/bin/env python3
"""넣은 Supabase 키가 안전한 것인지 검사한다.

키 값 자체는 절대 출력하지 않는다. 역할(role)과 판정만 보여준다.

실행:
    python3 scripts/check_env.py            # 형식만 검사 (네트워크 안 씀)
    python3 scripts/check_env.py --connect  # 실제 접속까지 확인
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def decode_jwt_role(token: str) -> str | None:
    """JWT 가운데 조각(payload)에서 role만 꺼낸다. 서명은 검증하지 않는다."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)  # base64url 패딩 복원
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None
    return data.get("role")


def classify(token: str) -> tuple[str, bool, str]:
    """(판정 이름, 안전한가, 설명)."""
    if token.startswith("sb_publishable_"):
        return "publishable (새 이름의 anon)", True, "브라우저에 노출돼도 되는 공개 키입니다."
    if token.startswith("sb_secret_"):
        return "secret (새 이름의 service_role)", False, "RLS를 우회합니다. 앱에 넣으면 안 됩니다."
    role = decode_jwt_role(token)
    if role == "anon":
        return "anon (JWT)", True, "브라우저에 노출돼도 되는 공개 키입니다."
    if role == "service_role":
        return "service_role (JWT)", False, "RLS를 우회합니다. 앱에 넣으면 안 됩니다."
    if role:
        return f"알 수 없는 role: {role}", False, "anon 키인지 다시 확인하세요."
    if re.fullmatch(r"[0-9a-fA-F]{64}", token):
        return (
            "JWT Secret 으로 보임 (64자 hex)",
            False,
            "이건 API 키가 아니라 토큰 서명 비밀입니다. 이걸로 아무 사용자든 위장할 수 있어\n"
            "       service_role보다 위험합니다. .env에서 지우고 anon 키를 다시 가져오세요.",
        )
    if token.startswith("https://"):
        return "URL 이 들어 있음", False, "키 칸에 주소를 붙이신 것 같습니다."
    return "형식을 알 수 없음", False, "키를 잘못 복사했을 수 있습니다(줄바꿈·공백 확인)."


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
        name, safe, note = classify(key)
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
