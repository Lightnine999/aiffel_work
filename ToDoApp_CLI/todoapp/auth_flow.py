"""로그인·로그아웃 흐름. CLI와 웹이 공유한다.

세션 보관 위치만 다르다 — CLI는 파일, 웹은 Flask 세션. 그래서 저장은
호출부가 하고, 여기서는 '토큰을 얻는 일'까지만 한다.
"""

from __future__ import annotations

import re

from todoapp.session import Tokens
from todoapp.supabase_client import (
    AuthError,
    attach_session,
    build_client,
    change_password,
    send_recovery_email,
    sign_in,
    sign_out,
    sign_up,
    verify_recovery_token,
)

# 메일 링크는 .../auth/v1/verify?token=<해시>&type=recovery&redirect_to=... 형태다.
# 사용자가 링크 전체를 붙여넣을 수도, 토큰만 뽑아올 수도 있어 둘 다 받는다.
_TOKEN_IN_URL_RE = re.compile(r"[?&]token=([^&#\s]+)")
_BARE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{16,}$")

# 계정이 없다는 뜻의 서버 응답들. 이건 사용자에게 알리지 않는다.
_NOT_FOUND_MARKERS = ("User not found", "user_not_found", "Unable to find user")


class NotLoggedIn(RuntimeError):
    """Supabase 저장소를 쓰는데 세션이 없다."""


def login(email: str, password: str) -> Tokens:
    """이메일·비밀번호로 로그인해 토큰을 얻는다."""
    if not email or not email.strip():
        raise AuthError("이메일을 입력하세요.")
    if not password:
        raise AuthError("비밀번호를 입력하세요.")
    return sign_in(build_client(), email.strip(), password)


def signup(email: str, password: str) -> Tokens:
    """계정을 만들고 토큰을 얻는다.

    이메일 확인(Confirm email)이 켜져 있으면 세션이 오지 않는다.
    그 경우 supabase_client가 끄는 방법을 안내하는 AuthError를 던진다.
    """
    if not email or not email.strip():
        raise AuthError("이메일을 입력하세요.")
    if len(password or "") < 6:
        raise AuthError("비밀번호는 6자 이상이어야 합니다.")
    return sign_up(build_client(), email.strip(), password)


def request_password_reset(email: str, redirect_to: str | None = None) -> None:
    """재설정 코드를 메일로 보낸다.

    **계정이 없어도 조용히 끝낸다.** 호출부는 언제나 같은 안내를 보여준다 —
    "보냈다"와 "그런 계정 없다"를 다르게 답하면, 공격자가 이메일을 하나씩
    넣어보며 어떤 주소가 가입돼 있는지 알아낼 수 있다(user enumeration).

    반면 발송 한도 초과는 계정 존재 여부와 무관하므로 그대로 알린다 —
    감추면 사용자가 왜 메일이 안 오는지 알 길이 없다.
    """
    if not email or not email.strip():
        raise AuthError("이메일을 입력하세요.")
    try:
        send_recovery_email(build_client(), email.strip(), redirect_to)
    except AuthError as exc:
        if any(marker in str(exc) for marker in _NOT_FOUND_MARKERS):
            return
        raise


def extract_recovery_token(link_or_token: str) -> str:
    """메일 링크에서 토큰을 뽑는다. 토큰만 줘도 그대로 받는다.

    링크 전체를 붙여넣는 사람이 대부분이라 URL 파싱을 먼저 시도한다.
    """
    value = (link_or_token or "").strip()
    if not value:
        raise AuthError("메일에 있는 링크 주소를 붙여넣으세요.")
    found = _TOKEN_IN_URL_RE.search(value)
    if found:
        return found.group(1)
    if _BARE_TOKEN_RE.match(value):
        return value
    raise AuthError(
        "링크에서 토큰을 찾지 못했습니다. 메일의 '비밀번호 재설정' 링크를 "
        "우클릭 → 링크 주소 복사 로 가져와 그대로 붙여넣으세요."
    )


def confirm_password_reset(link_or_token: str, new_password: str) -> Tokens:
    """메일 링크의 토큰으로 본인을 확인하고 비밀번호를 바꾼다.

    형식 검사를 서버에 보내기 전에 한다 — 무료 플랜의 요청 한도를 아끼고,
    사용자에게 즉시 안내할 수 있다.
    """
    token = extract_recovery_token(link_or_token)
    if len(new_password or "") < 6:
        raise AuthError("비밀번호는 6자 이상이어야 합니다.")
    client = build_client()
    tokens = verify_recovery_token(client, token)
    change_password(client, new_password)
    return tokens


def complete_password_reset_with_session(
    access_token: str, refresh_token: str, new_password: str
) -> Tokens:
    """웹 전용 — 메일 링크가 브라우저로 돌려준 세션으로 비밀번호를 바꾼다.

    Supabase는 링크를 검증한 뒤 우리 주소의 '#' 뒤에 토큰을 붙여 보낸다.
    서버는 '#' 뒤를 볼 수 없으므로 화면의 자바스크립트가 꺼내 넘겨준다.
    """
    if not access_token or not refresh_token:
        raise AuthError(
            "재설정 정보가 없습니다. 메일의 링크를 다시 눌러주세요. "
            "링크는 한 번만 쓸 수 있습니다."
        )
    if len(new_password or "") < 6:
        raise AuthError("비밀번호는 6자 이상이어야 합니다.")
    client = build_client()
    tokens = attach_session(client, Tokens(access_token, refresh_token))
    change_password(client, new_password)
    return tokens


def revoke() -> None:
    """서버 세션을 무효화한다. 로컬 정리는 호출부가 한다."""
    try:
        sign_out(build_client())
    except Exception:
        # 키 설정이 깨져 있어도 로컬 로그아웃은 되어야 한다
        pass
