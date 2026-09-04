"""로그인·로그아웃 흐름. CLI와 웹이 공유한다.

세션 보관 위치만 다르다 — CLI는 파일, 웹은 Flask 세션. 그래서 저장은
호출부가 하고, 여기서는 '토큰을 얻는 일'까지만 한다.
"""

from __future__ import annotations

from todoapp.session import Tokens
from todoapp.supabase_client import AuthError, build_client, sign_in, sign_out, sign_up


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


def revoke() -> None:
    """서버 세션을 무효화한다. 로컬 정리는 호출부가 한다."""
    try:
        sign_out(build_client())
    except Exception:
        # 키 설정이 깨져 있어도 로컬 로그아웃은 되어야 한다
        pass
