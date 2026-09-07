"""비밀번호 찾기 테스트. 가짜 인증으로 네트워크 없이 검증한다.

메일 링크 방식이다. 6자리 코드 방식은 쓸 수 없다 — Supabase 무료 플랜은
커스텀 SMTP 없이 메일 템플릿을 수정할 수 없고, 기본 템플릿에는 코드가 없다
(2026-09-07 대시보드에서 확인).
"""
from __future__ import annotations

import pytest

from todoapp.session import Tokens, load
from todoapp.supabase_client import AuthError

FAKE = Tokens("access-r", "refresh-r", "me@example.com", "uid-1")
NEW_PW = "새비밀번호123"
LINK = (
    "https://zocsvheggxbtczhdgple.supabase.co/auth/v1/verify"
    "?token=pkce_abc123DEF456ghi789&type=recovery"
    "&redirect_to=http://127.0.0.1:5000/reset/callback"
)


@pytest.fixture
def calls(monkeypatch):
    """supabase_client 함수들을 가짜로 바꾸고 호출을 기록한다."""
    log: dict = {"sent": [], "verified": [], "attached": [], "changed": []}

    def fake_send(client, email, redirect_to=None):
        if email == "없는사람@example.com":
            raise AuthError("User not found")
        if email == "너무자주@example.com":
            raise AuthError("요청이 너무 잦습니다. 잠시 후 다시 시도하세요.")
        log["sent"].append((email, redirect_to))

    def fake_verify_token(client, token_hash):
        if token_hash == "expired":
            raise AuthError("코드가 만료되었거나 올바르지 않습니다.")
        log["verified"].append(token_hash)
        return FAKE

    def fake_attach(client, tokens):
        if tokens.access_token == "bad":
            raise AuthError("세션이 만료되었습니다. 다시 로그인하세요.")
        log["attached"].append(tokens.access_token)
        return FAKE

    def fake_change(client, password):
        log["changed"].append(password)

    monkeypatch.setattr("todoapp.auth_flow.build_client", lambda: object())
    monkeypatch.setattr("todoapp.auth_flow.send_recovery_email", fake_send)
    monkeypatch.setattr("todoapp.auth_flow.verify_recovery_token", fake_verify_token)
    monkeypatch.setattr("todoapp.auth_flow.attach_session", fake_attach)
    monkeypatch.setattr("todoapp.auth_flow.change_password", fake_change)
    return log


# ---------------------------------------------------------------- 발송


class TestRequestReset:
    def test_링크를_보낸다(self, calls):
        from todoapp.auth_flow import request_password_reset

        request_password_reset("  me@example.com  ", redirect_to="http://x/cb")
        assert calls["sent"] == [("me@example.com", "http://x/cb")]

    def test_없는_계정도_조용히_끝난다(self, calls):
        """계정 존재 여부를 흘리면 안 된다 (user enumeration)."""
        from todoapp.auth_flow import request_password_reset

        request_password_reset("없는사람@example.com")
        assert calls["sent"] == []

    def test_요청이_너무_잦으면_알려준다(self, calls):
        """계정 존재 여부와 무관한 정보라 감추지 않는다."""
        from todoapp.auth_flow import request_password_reset

        with pytest.raises(AuthError, match="잠시 후"):
            request_password_reset("너무자주@example.com")

    def test_빈_이메일은_거부한다(self, calls):
        from todoapp.auth_flow import request_password_reset

        with pytest.raises(AuthError, match="이메일"):
            request_password_reset("   ")


class TestFriendlyMessages:
    """서버의 영어 오류를 한국어로 바꾸는 표. supabase_client 안에 있어
    가짜로 대체된 흐름 테스트로는 확인되지 않으므로 직접 검사한다."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Token has expired or is invalid", "만료"),
            ("For security purposes, you can only request this after 47s", "잠시 후"),
            ("over_email_send_rate_limit", "한도"),
            ("New password should be different from the old password", "이전과 다른"),
            ("Auth session missing!", "세션이 없습니다"),
        ],
    )
    def test_한국어로_바꾼다(self, raw, expected):
        from todoapp.supabase_client import _friendly

        assert expected in _friendly(Exception(raw))


# ---------------------------------------------------------------- 링크 파싱


class TestExtractToken:
    def test_링크에서_토큰을_뽑는다(self):
        from todoapp.auth_flow import extract_recovery_token

        assert extract_recovery_token(LINK) == "pkce_abc123DEF456ghi789"

    def test_앞뒤_공백을_다듬는다(self):
        from todoapp.auth_flow import extract_recovery_token

        assert extract_recovery_token(f"  {LINK}  ") == "pkce_abc123DEF456ghi789"

    def test_토큰만_줘도_받는다(self):
        from todoapp.auth_flow import extract_recovery_token

        assert extract_recovery_token("pkce_abc123DEF456ghi789") == "pkce_abc123DEF456ghi789"

    def test_뒤에_다른_인자가_붙어도_토큰만_가른다(self):
        from todoapp.auth_flow import extract_recovery_token

        assert extract_recovery_token(LINK + "&extra=1") == "pkce_abc123DEF456ghi789"

    @pytest.mark.parametrize("bad", ["", "   ", "그냥 문장", "https://example.com/no-token"])
    def test_토큰이_없으면_안내한다(self, bad):
        from todoapp.auth_flow import extract_recovery_token

        with pytest.raises(AuthError):
            extract_recovery_token(bad)


# ---------------------------------------------------------------- 완료 (CLI 경로)


class TestConfirmByLink:
    def test_링크와_새_비밀번호로_바꾼다(self, calls):
        from todoapp.auth_flow import confirm_password_reset

        tokens = confirm_password_reset(LINK, NEW_PW)
        assert tokens == FAKE
        assert calls["verified"] == ["pkce_abc123DEF456ghi789"]
        assert calls["changed"] == [NEW_PW]

    @pytest.mark.parametrize("short", ["", "12345", "abc"])
    def test_짧은_비밀번호는_서버에_보내지_않는다(self, calls, short):
        from todoapp.auth_flow import confirm_password_reset

        with pytest.raises(AuthError, match="6자 이상"):
            confirm_password_reset(LINK, short)
        assert calls["verified"] == []

    def test_만료된_링크는_비밀번호를_바꾸지_않는다(self, calls):
        from todoapp.auth_flow import confirm_password_reset

        with pytest.raises(AuthError):
            confirm_password_reset("https://x/verify?token=expired&type=recovery", NEW_PW)
        assert calls["changed"] == []


# ---------------------------------------------------------------- 완료 (웹 경로)


class TestCompleteWithSession:
    def test_세션_토큰으로_바꾼다(self, calls):
        from todoapp.auth_flow import complete_password_reset_with_session

        tokens = complete_password_reset_with_session("acc", "ref", NEW_PW)
        assert tokens == FAKE
        assert calls["attached"] == ["acc"]
        assert calls["changed"] == [NEW_PW]

    @pytest.mark.parametrize("acc,ref", [("", "ref"), ("acc", ""), ("", "")])
    def test_토큰이_없으면_안내한다(self, calls, acc, ref):
        from todoapp.auth_flow import complete_password_reset_with_session

        with pytest.raises(AuthError, match="다시 눌러"):
            complete_password_reset_with_session(acc, ref, NEW_PW)
        assert calls["changed"] == []

    def test_짧은_비밀번호는_거부한다(self, calls):
        from todoapp.auth_flow import complete_password_reset_with_session

        with pytest.raises(AuthError, match="6자 이상"):
            complete_password_reset_with_session("acc", "ref", "12345")
        assert calls["attached"] == []


# ---------------------------------------------------------------- CLI


@pytest.fixture
def session_path(tmp_path, monkeypatch):
    path = tmp_path / "cfg" / "session.json"
    monkeypatch.setattr("todoapp.session.SESSION_PATH", path)
    monkeypatch.setattr("todoapp.cli.SESSION_PATH", path)
    return path


class TestCliResetPassword:
    def _answers(self, monkeypatch, link=LINK, pw=NEW_PW, again=None):
        typed = iter([link])
        secrets = iter([pw, again if again is not None else pw])
        monkeypatch.setattr("builtins.input", lambda *a: next(typed))
        monkeypatch.setattr("todoapp.cli.getpass.getpass", lambda *a: next(secrets))

    def test_한_명령으로_끝난다(self, calls, session_path, monkeypatch, capsys):
        from todoapp.cli import main

        self._answers(monkeypatch)
        assert main(["reset-password", "--email", "me@example.com"]) == 0
        assert calls["changed"] == [NEW_PW]
        assert load(session_path) == FAKE  # 바로 로그인 상태가 된다

    def test_링크를_누르지_말라고_안내한다(self, calls, session_path, monkeypatch, capsys):
        from todoapp.cli import main

        self._answers(monkeypatch)
        main(["reset-password", "--email", "me@example.com"])
        out = capsys.readouterr().out
        assert "누르지" in out and "링크 주소 복사" in out

    def test_새_비밀번호를_두_번_확인한다(self, calls, session_path, monkeypatch, capsys):
        from todoapp.cli import main

        self._answers(monkeypatch, again="다른비밀번호123")
        assert main(["reset-password", "--email", "me@example.com"]) == 1
        assert "일치하지" in capsys.readouterr().err
        assert calls["changed"] == []

    def test_비밀번호가_화면에_안_찍힌다(self, calls, session_path, monkeypatch, capsys):
        from todoapp.cli import main

        self._answers(monkeypatch)
        main(["reset-password", "--email", "me@example.com"])
        captured = capsys.readouterr()
        assert NEW_PW not in captured.out and NEW_PW not in captured.err

    def test_없는_계정도_같은_안내를_보여준다(self, calls, session_path, monkeypatch, capsys):
        from todoapp.cli import main

        self._answers(monkeypatch)
        main(["reset-password", "--email", "없는사람@example.com"])
        assert "보냈습니다" in capsys.readouterr().out


# ---------------------------------------------------------------- 웹


@pytest.fixture
def client(monkeypatch):
    from todoapp.web import create_app

    class FakeTodos:
        def list(self, **k):
            return []

        def get(self, todo_id):
            return None

        def count_all(self):
            return 0

    class FakeTags:
        def list_all(self):
            return []

    class FakeStore:
        def __init__(self):
            self.todos = FakeTodos()
            self.tags = FakeTags()

        def transaction(self):
            from contextlib import nullcontext

            return nullcontext()

    monkeypatch.setattr("todoapp.web.build_store", lambda *a, **k: FakeStore())
    app = create_app(secret_key="테스트키", backend="supabase", today=lambda: "2026-09-07")
    return app.test_client()


class TestWebResetPassword:
    def test_로그인_없이_열린다(self, client, calls):
        assert client.get("/reset").status_code == 200
        assert client.get("/reset/callback").status_code == 200

    def test_로그인_화면에_링크가_있다(self, client, calls):
        assert "/reset" in client.get("/login").get_data(as_text=True)

    def test_메일을_보내면_안내_화면이_뜬다(self, client, calls):
        body = client.post("/reset", data={"email": "me@example.com"}).get_data(as_text=True)
        assert "메일을 보냈습니다" in body
        assert "스팸함" in body
        (sent_email, redirect_to) = calls["sent"][0]
        assert sent_email == "me@example.com"
        assert redirect_to.endswith("/reset/callback")  # 우리 앱으로 돌아오게 한다

    def test_없는_계정도_같은_화면을_보여준다(self, client, calls):
        body = client.post("/reset", data={"email": "없는사람@example.com"}).get_data(as_text=True)
        assert "메일을 보냈습니다" in body

    def test_콜백_화면이_해시_토큰을_읽는_스크립트를_담는다(self, client, calls):
        """서버는 '#' 뒤를 볼 수 없어 자바스크립트가 꺼내야 한다."""
        body = client.get("/reset/callback").get_data(as_text=True)
        assert "location.hash" in body
        assert "access_token" in body
        assert "history.replaceState" in body  # 주소창에 토큰을 남기지 않는다

    def test_토큰과_새_비밀번호로_바꾸면_로그인된다(self, client, calls):
        response = client.post(
            "/reset/callback",
            data={"access_token": "acc", "refresh_token": "ref",
                  "password": NEW_PW, "password2": NEW_PW},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")
        assert calls["changed"] == [NEW_PW]
        assert client.get("/").status_code == 200  # 로그인 상태

    def test_비밀번호_확인이_다르면_거부한다(self, client, calls):
        body = client.post(
            "/reset/callback",
            data={"access_token": "acc", "refresh_token": "ref",
                  "password": NEW_PW, "password2": "다른비밀번호123"},
        ).get_data(as_text=True)
        assert "일치하지" in body
        assert calls["changed"] == []

    def test_실패해도_비밀번호는_화면에_안_남는다(self, client, calls):
        body = client.post(
            "/reset/callback",
            data={"access_token": "bad", "refresh_token": "ref",
                  "password": NEW_PW, "password2": NEW_PW},
        ).get_data(as_text=True)
        assert NEW_PW not in body

    def test_토큰이_없으면_다시_받으라고_안내한다(self, client, calls):
        body = client.post(
            "/reset/callback",
            data={"access_token": "", "refresh_token": "",
                  "password": NEW_PW, "password2": NEW_PW},
        ).get_data(as_text=True)
        assert "다시 눌러" in body
        assert calls["changed"] == []
