"""Supabase 키가 어떤 종류인지 판정한다.

앱(config.py)과 검사기(scripts/check_env.py)가 같은 판정을 쓴다.
두 곳에 따로 두면 규칙이 갈라진다.

키 값을 로그나 예외 메시지에 담지 않는다 — 판정 이름만 담는다.
"""

from __future__ import annotations

import base64
import json
import re

_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def decode_jwt_role(token: str) -> str | None:
    """JWT payload에서 role만 꺼낸다. 서명은 검증하지 않는다."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1] + "=" * (-len(parts[1]) % 4)  # base64url 패딩 복원
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None
    role = data.get("role")
    return str(role) if role else None


def classify_key(token: str) -> tuple[str, bool, str]:
    """(판정 이름, 앱에서 써도 되는가, 설명)."""
    if not token:
        return "비어 있음", False, "키가 설정되지 않았습니다."
    if token.startswith("https://"):
        return "URL 이 들어 있음", False, "키 칸에 주소를 붙이신 것 같습니다."
    if token.startswith("sb_publishable_"):
        return (
            "publishable (새 이름의 anon)",
            True,
            "브라우저에 노출돼도 되는 공개 키입니다.",
        )
    if token.startswith("sb_secret_"):
        return (
            "secret (새 이름의 service_role)",
            False,
            "RLS를 우회합니다. 앱에 넣으면 안 됩니다.",
        )
    role = decode_jwt_role(token)
    if role == "anon":
        return "anon (JWT)", True, "브라우저에 노출돼도 되는 공개 키입니다."
    if role == "service_role":
        return (
            "service_role (JWT)",
            False,
            "RLS를 우회합니다. 앱에 넣으면 안 됩니다.",
        )
    if role:
        return f"알 수 없는 role: {role}", False, "anon 키인지 다시 확인하세요."
    if _HEX64_RE.match(token):
        return (
            "JWT Secret 으로 보임 (64자 hex)",
            False,
            "이건 API 키가 아니라 토큰 서명 비밀입니다. 이걸로 아무 사용자든 위장할 수 "
            "있어 service_role보다 위험합니다. .env에서 지우고 anon 키를 다시 가져오세요.",
        )
    return "형식을 알 수 없음", False, "키를 잘못 복사했을 수 있습니다(줄바꿈·공백 확인)."
