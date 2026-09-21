"""CLI 로그인·로그아웃·저장소 선택 테스트. 네트워크를 쓰지 않는다."""
from __future__ import annotations

import pytest

from todoapp.cli import main
from todoapp.session import Tokens, load, save
from todoapp.supabase_client import AuthError

FAKE = Tokens("access-1", "refresh-1", "me@example.com", "uid-1")


@pytest.fixture
def session_path(tmp_path, monkeypatch):
    """세션 파일을 임시 경로로 돌린다. 실제 ~/.config를 건드리면 안 된다."""
    path = tmp_path / "cfg" / "session.json"
    monkeypatch.setattr("todoapp.session.SESSION_PATH", path)
    monkeypatch.setattr("todoapp.cli.SESSION_PATH", path, raising=False)
    return path


@pytest.fixture
def fake_auth(monkeypatch):
    """로그인·회원가입을 가짜로 바꾼다. 호출 인자를 기록한다."""
    calls = {}

    def fake_login(email, password):
        calls["login"] = (email, password)
        if password == "틀린비밀번호":
            raise AuthError("이메일 또는 비밀번호가 맞지 않습니다.")
        return FAKE

    def fake_signup(email, password):
        calls["signup"] = (email, password)
        return FAKE

    def fake_revoke():
        calls["revoke"] = True

    monkeypatch.setattr("todoapp.cli.auth_flow.login", fake_login)
    monkeypatch.setattr("todoapp.cli.auth_flow.signup", fake_signup)
    monkeypatch.setattr("todoapp.cli.auth_flow.revoke", fake_revoke)
    return calls


def run(*argv, **kwargs):
    return main(list(argv), **kwargs)


class TestLogin:
    def test_로그인하면_세션이_저장된다(self, session_path, fake_auth, capsys):
        code = run("login", "--email", "me@example.com", "--password", "비밀번호123")
        assert code == 0
        assert load(session_path) == FAKE
        assert "me@example.com" in capsys.readouterr().out

    def test_비밀번호를_인자로_안_주면_getpass로_받는다(
        self, session_path, fake_auth, monkeypatch, capsys
    ):
        monkeypatch.setattr("todoapp.cli.getpass.getpass", lambda *a: "물어본비밀번호")
        run("login", "--email", "me@example.com")
        assert fake_auth["login"] == ("me@example.com", "물어본비밀번호")

    def test_이메일도_안_주면_물어본다(self, session_path, fake_auth, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda *a: "asked@example.com")
        monkeypatch.setattr("todoapp.cli.getpass.getpass", lambda *a: "pw")
        run("login")
        assert fake_auth["login"][0] == "asked@example.com"

    def test_실패하면_1을_돌려주고_세션을_만들지_않는다(
        self, session_path, fake_auth, capsys
    ):
        code = run("login", "--email", "me@example.com", "--password", "틀린비밀번호")
        assert code == 1
        assert load(session_path) is None
        assert "맞지 않습니다" in capsys.readouterr().err

    def test_비밀번호가_화면에_찍히지_않는다(self, session_path, fake_auth, capsys):
        run("login", "--email", "me@example.com", "--password", "비밀번호123")
        captured = capsys.readouterr()
        assert "비밀번호123" not in captured.out
        assert "비밀번호123" not in captured.err


class TestSignup:
    def test_가입하면_세션이_저장된다(self, session_path, fake_auth, capsys):
        assert run("signup", "--email", "new@example.com", "--password", "비밀번호123") == 0
        assert load(session_path) == FAKE
        assert fake_auth["signup"] == ("new@example.com", "비밀번호123")


class TestLogoutAndWhoami:
    def test_로그아웃하면_세션이_지워진다(self, session_path, fake_auth, capsys):
        save(FAKE, session_path)
        assert run("logout") == 0
        assert load(session_path) is None
        assert fake_auth.get("revoke") is True

    def test_로그인_안_했는데_로그아웃해도_0이다(self, session_path, fake_auth, capsys):
        assert run("logout") == 0
        assert "로그인" in capsys.readouterr().out

    def test_whoami는_이메일을_보여준다(self, session_path, capsys):
        save(FAKE, session_path)
        assert run("whoami") == 0
        assert "me@example.com" in capsys.readouterr().out

    def test_로그인_안_했으면_whoami가_알려준다(self, session_path, capsys):
        assert run("whoami") == 0
        out = capsys.readouterr().out
        assert "로그인" in out

    def test_whoami가_토큰을_출력하지_않는다(self, session_path, capsys):
        save(FAKE, session_path)
        run("whoami")
        captured = capsys.readouterr().out
        assert "access-1" not in captured
        assert "refresh-1" not in captured


class TestStorageSelection:
    def test_sqlite면_로그인_없이_동작한다(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setenv("STORAGE", "sqlite")
        monkeypatch.setenv("DB_PATH", str(tmp_path / "cli.db"))
        monkeypatch.setattr("todoapp.config.load_dotenv", lambda *a, **k: None)
        assert run("add", "장보기") == 0
        assert run("list") == 0
        assert "장보기" in capsys.readouterr().out

    def test_supabase인데_로그인_안_했으면_안내하고_1을_돌려준다(
        self, monkeypatch, session_path, capsys
    ):
        monkeypatch.setenv("STORAGE", "supabase")
        monkeypatch.setattr("todoapp.config.load_dotenv", lambda *a, **k: None)
        assert run("list") == 1
        assert "login" in capsys.readouterr().err

    def test_supabase에서_갱신된_토큰을_다시_저장한다(
        self, monkeypatch, session_path, capsys
    ):
        """만료된 access token이 갱신되면 파일도 갱신되어야 한다.

        안 하면 매번 갱신 왕복이 한 번씩 더 든다.
        """
        refreshed = Tokens("access-2", "refresh-2", "me@example.com", "uid-1")
        save(FAKE, session_path)

        class FakeStore:
            tokens = refreshed
            todos = tags = None

            def create_todo(self, *a, **k):
                return 1

            def set_tags(self, *a, **k):
                pass

            def transaction(self):
                from contextlib import nullcontext

                return nullcontext()

        monkeypatch.setenv("STORAGE", "supabase")
        monkeypatch.setattr("todoapp.config.load_dotenv", lambda *a, **k: None)
        monkeypatch.setattr("todoapp.cli.build_store", lambda *a, **k: FakeStore())
        monkeypatch.setattr("todoapp.cli.TodoService", lambda store, **k: _StubService())
        run("tags")
        assert load(session_path) == refreshed


class _StubService:
    def all_tags(self):
        return []

    def today(self):
        return "2026-09-04"
