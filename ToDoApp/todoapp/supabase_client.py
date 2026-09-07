"""Supabase 클라이언트 생성과 인증.

로그인·회원가입은 supabase-py(GoTrue)에 맡긴다. 비밀번호 해싱·토큰 발급을
직접 만들지 않는다 — PRD의 "로그인은 검증된 라이브러리로"를 이렇게 충족한다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from todoapp.config import get_supabase_anon_key, get_supabase_url
from todoapp.session import Tokens

if TYPE_CHECKING:  # 런타임에 supabase를 강제로 import하지 않는다
    from supabase import Client


class AuthError(RuntimeError):
    """로그인·회원가입 실패. 사용자에게 보여줄 문구를 담는다."""


def build_client() -> "Client":
    """anon 키로 클라이언트를 만든다. 키 검증은 config가 한다."""
    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover
        raise AuthError(
            "supabase 패키지가 없습니다: python3 -m pip install -r requirements.txt"
        ) from exc
    return create_client(get_supabase_url(), get_supabase_anon_key())


def _tokens_from_response(response, email: str | None = None) -> Tokens:
    session = getattr(response, "session", None)
    if session is None or not getattr(session, "access_token", None):
        raise AuthError(
            "세션을 받지 못했습니다. 이메일 확인(Confirm email)이 켜져 있으면 "
            "메일의 링크를 먼저 눌러야 합니다. "
            "학습용이면 대시보드 > Authentication > Sign In / Providers > Email 에서 끄세요."
        )
    user = getattr(response, "user", None)
    return Tokens(
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        email=getattr(user, "email", None) or email,
        user_id=getattr(user, "id", None),
    )


def sign_in(client: "Client", email: str, password: str) -> Tokens:
    try:
        response = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception as exc:
        raise AuthError(f"로그인 실패: {_friendly(exc)}") from exc
    return _tokens_from_response(response, email)


def sign_up(client: "Client", email: str, password: str) -> Tokens:
    try:
        response = client.auth.sign_up({"email": email, "password": password})
    except Exception as exc:
        raise AuthError(f"회원가입 실패: {_friendly(exc)}") from exc
    return _tokens_from_response(response, email)


def attach_session(client: "Client", tokens: Tokens) -> Tokens:
    """저장된 토큰을 클라이언트에 물린다. 만료됐으면 한 번 갱신한다.

    갱신도 실패하면 AuthError를 던진다 — 호출부가 세션을 비우고 재로그인을 요구한다.
    """
    try:
        response = client.auth.set_session(tokens.access_token, tokens.refresh_token)
        return _tokens_from_response(response, tokens.email)
    except Exception:
        pass
    try:
        response = client.auth.refresh_session(tokens.refresh_token)
        return _tokens_from_response(response, tokens.email)
    except Exception as exc:
        raise AuthError("세션이 만료되었습니다. 다시 로그인하세요.") from exc


def send_recovery_email(client: "Client", email: str, redirect_to: str | None = None) -> None:
    """비밀번호 재설정 메일을 보낸다.

    Supabase는 존재하지 않는 이메일에도 성공을 돌려준다 — 계정 존재 여부를
    흘리지 않기 위한 설계다. 우리도 그 태도를 유지한다 (auth_flow 참고).
    """
    options = {"redirect_to": redirect_to} if redirect_to else None
    try:
        client.auth.reset_password_for_email(email, options)
    except Exception as exc:
        raise AuthError(_friendly(exc)) from exc


def verify_recovery_token(client: "Client", token_hash: str) -> Tokens:
    """메일 링크에 실린 토큰을 확인하고 세션을 받는다.

    링크는 한 번만 쓸 수 있다 — 브라우저에서 이미 눌렀다면 그 토큰은 소진된다.
    그래서 CLI에서는 '누르지 말고 주소를 복사'해야 한다.
    """
    try:
        response = client.auth.verify_otp(
            {"token_hash": token_hash, "type": "recovery"}
        )
    except Exception as exc:
        raise AuthError(_friendly(exc)) from exc
    return _tokens_from_response(response)


def change_password(client: "Client", new_password: str) -> None:
    """현재 세션의 비밀번호를 바꾼다. 본인 확인(토큰 검증·세션 부착) 직후에 부른다."""
    try:
        client.auth.update_user({"password": new_password})
    except Exception as exc:
        raise AuthError(_friendly(exc)) from exc


def sign_out(client: "Client") -> None:
    try:
        client.auth.sign_out()
    except Exception:
        # 서버에서 이미 무효화된 세션일 수 있다. 로컬 정리가 본질이므로 넘어간다.
        pass


def _friendly(exc: Exception) -> str:
    """서버 오류 문구를 한국어 안내로 바꾼다."""
    message = str(exc)
    table = {
        "Invalid login credentials": "이메일 또는 비밀번호가 맞지 않습니다.",
        "Email not confirmed": "이메일 확인이 끝나지 않았습니다. 메일의 링크를 눌러주세요.",
        "User already registered": "이미 가입된 이메일입니다. 로그인하세요.",
        "Password should be at least": "비밀번호가 너무 짧습니다 (최소 6자).",
        "Unable to validate email address": "이메일 형식이 올바르지 않습니다.",
        "Token has expired or is invalid": "코드가 만료되었거나 올바르지 않습니다. 다시 요청하세요.",
        "otp_expired": "코드가 만료되었습니다. 다시 요청하세요.",
        "For security purposes": "요청이 너무 잦습니다. 잠시 후 다시 시도하세요.",
        "over_email_send_rate_limit": "메일 발송 한도를 넘었습니다. 잠시 후 다시 시도하세요.",
        "New password should be different": "이전과 다른 비밀번호를 쓰세요.",
        "Auth session missing": "세션이 없습니다. 코드 확인부터 다시 하세요.",
    }
    for needle, friendly in table.items():
        if needle in message:
            return friendly
    return message[:200]
