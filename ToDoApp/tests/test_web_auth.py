"""웹 로그인 흐름 테스트. 가짜 인증으로 네트워크 없이 검증한다."""
from __future__ import annotations

import pytest

from todoapp.session import Tokens
from todoapp.supabase_client import AuthError
from todoapp.web import create_app

FAKE = Tokens("access-1", "refresh-1", "me@example.com", "uid-1")


class FakeStore:
    """로그인 후 화면이 열리는지만 보는 최소 저장소."""

    def __init__(self):
        self.todos = _FakeTodos()
        self.tags = _FakeTags()
        self.tokens = FAKE

    def create_todo(self, *a, **k):
        return 1

    def set_tags(self, *a, **k):
        pass

    def transaction(self):
        from contextlib import nullcontext

        return nullcontext()


class _FakeTodos:
    def list(self, **k):
        return []

    def get(self, todo_id):
        return None

    def count_all(self):
        return 0

    def set_done(self, *a):
        return False

    def delete(self, *a):
        return False

    def update(self, *a, **k):
        return False


class _FakeTags:
    def list_all(self):
        return []


@pytest.fixture
def cloud_app(monkeypatch):
    """Supabase 저장소를 쓰는 앱. 실제 접속은 하지 않는다."""
    monkeypatch.setattr("todoapp.stores.build_store", lambda *a, **k: FakeStore())
    monkeypatch.setattr("todoapp.web.build_store", lambda *a, **k: FakeStore())
    return create_app(secret_key="테스트키", backend="supabase", today=lambda: "2026-09-04")


@pytest.fixture
def client(cloud_app):
    return cloud_app.test_client()


@pytest.fixture
def fake_auth(monkeypatch):
    calls = {}

    def fake_login(email, password):
        calls["login"] = (email, password)
        if password == "틀림":
            raise AuthError("이메일 또는 비밀번호가 맞지 않습니다.")
        return FAKE

    def fake_signup(email, password):
        calls["signup"] = (email, password)
        return FAKE

    monkeypatch.setattr("todoapp.web.routes.auth_flow.login", fake_login)
    monkeypatch.setattr("todoapp.web.routes.auth_flow.signup", fake_signup)
    monkeypatch.setattr("todoapp.web.routes.auth_flow.revoke", lambda: calls.setdefault("revoke", True))
    return calls


class TestGuard:
    def test_로그인_안_하면_로그인_화면으로_보낸다(self, client):
        response = client.get("/")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_로그인_화면은_로그인_없이_열린다(self, client):
        assert client.get("/login").status_code == 200

    def test_회원가입_화면도_열린다(self, client):
        assert client.get("/signup").status_code == 200

    def test_돌아갈_주소를_기억한다(self, client):
        response = client.get("/?scope=today")
        assert "next=" in response.headers["Location"]

    def test_변경_요청도_막힌다(self, client):
        response = client.post("/todos", data={"title": "몰래 추가"})
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


class TestSqliteBackendSkipsLogin:
    def test_로컬_저장소는_로그인을_요구하지_않는다(self, db_path):
        app = create_app(db_path=db_path, secret_key="키", today=lambda: "2026-09-04")
        assert app.test_client().get("/").status_code == 200

    def test_로컬_저장소에서_로그인_화면은_목록으로_보낸다(self, db_path):
        app = create_app(db_path=db_path, secret_key="키")
        response = app.test_client().get("/login")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")


class TestLoginFlow:
    def test_로그인하면_목록으로_간다(self, client, fake_auth):
        response = client.post(
            "/login", data={"email": "me@example.com", "password": "비밀번호123"}
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")
        assert fake_auth["login"] == ("me@example.com", "비밀번호123")

    def test_로그인_후_목록이_열린다(self, client, fake_auth):
        client.post("/login", data={"email": "me@example.com", "password": "pw123456"})
        assert client.get("/").status_code == 200

    def test_실패하면_같은_화면에_안내가_뜬다(self, client, fake_auth):
        response = client.post(
            "/login", data={"email": "me@example.com", "password": "틀림"}
        )
        assert response.status_code == 200
        assert "맞지 않습니다" in response.get_data(as_text=True)

    def test_실패해도_이메일은_남고_비밀번호는_안_남는다(self, client, fake_auth):
        response = client.post(
            "/login", data={"email": "me@example.com", "password": "틀림"}
        )
        body = response.get_data(as_text=True)
        assert "me@example.com" in body
        assert "틀림" not in body

    def test_회원가입도_동작한다(self, client, fake_auth):
        response = client.post(
            "/signup", data={"email": "new@example.com", "password": "비밀번호123"}
        )
        assert response.status_code == 302
        assert fake_auth["signup"] == ("new@example.com", "비밀번호123")


class TestLogout:
    def test_로그아웃하면_다시_막힌다(self, client, fake_auth):
        client.post("/login", data={"email": "me@example.com", "password": "pw123456"})
        assert client.get("/").status_code == 200
        assert client.post("/logout").status_code == 302
        assert fake_auth.get("revoke") is True
        assert client.get("/").status_code == 302  # 다시 로그인 화면으로

    def test_로그아웃은_GET으로_안_된다(self, client, fake_auth):
        assert client.get("/logout").status_code == 405


class TestTokenExposure:
    def test_토큰이_화면에_찍히지_않는다(self, client, fake_auth):
        client.post("/login", data={"email": "me@example.com", "password": "pw123456"})
        body = client.get("/").get_data(as_text=True)
        assert "access-1" not in body
        assert "refresh-1" not in body

    def test_계정_이메일은_보여준다(self, client, fake_auth):
        client.post("/login", data={"email": "me@example.com", "password": "pw123456"})
        assert "me@example.com" in client.get("/").get_data(as_text=True)
