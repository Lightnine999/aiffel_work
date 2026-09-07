"""키 판정·설정 가드·세션 저장소 테스트. 네트워크를 쓰지 않는다."""
from __future__ import annotations

import base64
import json
import os
import stat

import pytest

from todoapp.keycheck import classify_key, decode_jwt_role
from todoapp.session import Tokens, clear, load, save


def fake_jwt(role: str) -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"role": role, "iss": "supabase"}).encode()
    ).decode().rstrip("=")
    return f"eyJhbGciOiJIUzI1NiJ9.{payload}.signature"


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    """실제 .env를 읽지 않게 막는다. 테스트가 대표님 설정에 좌우되면 안 된다."""
    monkeypatch.setattr("todoapp.config.load_dotenv", lambda *a, **k: None)


class TestClassifyKey:
    @pytest.mark.parametrize(
        "token,expected_safe",
        [
            (fake_jwt("anon"), True),
            ("sb_publishable_abc123def456", True),
            (fake_jwt("service_role"), False),
            ("sb_secret_abc123def456", False),
            ("a" * 64, False),  # JWT Secret 형태
            ("https://xxx.supabase.co", False),
            ("", False),
            ("garbage", False),
        ],
    )
    def test_안전_여부를_가른다(self, token, expected_safe):
        _, safe, _ = classify_key(token)
        assert safe is expected_safe

    def test_JWT_Secret을_이름으로_알려준다(self):
        name, safe, note = classify_key("0" * 64)
        assert "JWT Secret" in name
        assert safe is False
        assert "위험" in note

    def test_URL_오입력을_알려준다(self):
        name, _, _ = classify_key("https://x.supabase.co")
        assert "URL" in name

    def test_role을_읽는다(self):
        assert decode_jwt_role(fake_jwt("anon")) == "anon"
        assert decode_jwt_role("not.a.jwt") is None
        assert decode_jwt_role("only-one-part") is None


class TestConfigGuards:
    def test_URL이_없으면_throw(self, monkeypatch):
        from todoapp.config import get_supabase_url

        monkeypatch.delenv("SUPABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="SUPABASE_URL"):
            get_supabase_url()

    def test_키가_없으면_throw(self, monkeypatch):
        from todoapp.config import get_supabase_anon_key

        monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
        with pytest.raises(RuntimeError, match="SUPABASE_ANON_KEY"):
            get_supabase_anon_key()

    def test_anon_키는_통과한다(self, monkeypatch):
        from todoapp.config import get_supabase_anon_key

        token = fake_jwt("anon")
        monkeypatch.setenv("SUPABASE_ANON_KEY", token)
        assert get_supabase_anon_key() == token

    @pytest.mark.parametrize(
        "bad", [fake_jwt("service_role"), "sb_secret_xxx", "b" * 64]
    )
    def test_위험한_키는_거부한다(self, monkeypatch, bad):
        from todoapp.config import get_supabase_anon_key

        monkeypatch.setenv("SUPABASE_ANON_KEY", bad)
        with pytest.raises(RuntimeError, match="안전하지 않습니다"):
            get_supabase_anon_key()

    def test_거부_메시지에_키_값이_담기지_않는다(self, monkeypatch):
        from todoapp.config import get_supabase_anon_key

        secret = "c" * 64
        monkeypatch.setenv("SUPABASE_ANON_KEY", secret)
        with pytest.raises(RuntimeError) as exc:
            get_supabase_anon_key()
        assert secret not in str(exc.value)

    def test_service_role_변수가_있으면_앱이_멈춘다(self, monkeypatch):
        from todoapp.config import assert_no_service_role

        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "무엇이든")
        with pytest.raises(RuntimeError, match="RLS를 우회"):
            assert_no_service_role()

    def test_이름이_달라도_잡는다(self, monkeypatch):
        from todoapp.config import assert_no_service_role

        monkeypatch.setenv("MY_service_role_TOKEN", "무엇이든")
        with pytest.raises(RuntimeError):
            assert_no_service_role()

    def test_없으면_통과한다(self, monkeypatch):
        from todoapp.config import assert_no_service_role

        for name in list(os.environ):
            if "SERVICE_ROLE" in name.upper():
                monkeypatch.delenv(name, raising=False)
        assert_no_service_role()  # 예외 없음


class TestSessionStore:
    @pytest.fixture
    def path(self, tmp_path):
        return tmp_path / "cfg" / "session.json"

    def test_저장하고_읽는다(self, path):
        tokens = Tokens("access-1", "refresh-1", "me@example.com", "uid-1")
        save(tokens, path)
        assert load(path) == tokens

    def test_파일_권한이_0600이다(self, path):
        save(Tokens("a", "r"), path)
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600, f"실제 권한: {oct(mode)}"

    def test_디렉터리_권한이_0700이다(self, path):
        save(Tokens("a", "r"), path)
        mode = stat.S_IMODE(path.parent.stat().st_mode)
        assert mode == 0o700, f"실제 권한: {oct(mode)}"

    def test_넉넉한_권한의_기존_파일을_다시_잠근다(self, path):
        save(Tokens("a", "r"), path)
        path.chmod(0o644)
        save(Tokens("b", "r2"), path)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_없으면_None이다(self, path):
        assert load(path) is None

    def test_깨진_파일은_None이다(self, path):
        path.parent.mkdir(parents=True)
        path.write_text("{ 망가진 json", encoding="utf-8")
        assert load(path) is None

    def test_토큰이_빠진_파일은_None이다(self, path):
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"email": "x@y.com"}), encoding="utf-8")
        assert load(path) is None

    def test_지운다(self, path):
        save(Tokens("a", "r"), path)
        assert clear(path) is True
        assert load(path) is None
        assert clear(path) is False
