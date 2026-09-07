"""설정 로딩. 값은 .env에서만 읽는다."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "db" / "todo.db"


def get_db_path() -> Path:
    """DB 파일 경로. .env의 DB_PATH가 있으면 그것, 없으면 db/todo.db."""
    load_dotenv(PROJECT_ROOT / ".env")
    raw = os.getenv("DB_PATH", "").strip()
    path = Path(raw) if raw else DEFAULT_DB_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def get_secret_key() -> str:
    """Flask 세션 키. .env의 FLASK_SECRET_KEY에서만 읽는다.

    기본값을 두지 않는 이유: 하드코딩된 기본 키는 세션 위조를 허용한다.
    없으면 대충 넘기지 말고 즉시 멈춘다.
    """
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.getenv("FLASK_SECRET_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "FLASK_SECRET_KEY가 설정되지 않았습니다. "
            ".env.example을 .env로 복사한 뒤 값을 채우세요.\n"
            '  생성: python3 -c "import secrets; print(secrets.token_hex(32))"'
        )
    return key


VALID_BACKENDS = ("sqlite", "supabase")


def get_storage_backend() -> str:
    """어느 저장소를 쓸지. .env의 STORAGE. 없으면 sqlite(로컬)."""
    load_dotenv(PROJECT_ROOT / ".env")
    name = os.getenv("STORAGE", "sqlite").strip().lower() or "sqlite"
    if name not in VALID_BACKENDS:
        raise RuntimeError(
            f"STORAGE 값이 잘못되었습니다: {name!r} "
            f"(가능: {', '.join(VALID_BACKENDS)})"
        )
    return name


def _require(name: str, hint: str) -> str:
    """.env에서 필수 값을 읽는다. 기본값을 두지 않는다."""
    load_dotenv(PROJECT_ROOT / ".env")
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} 가 설정되지 않았습니다. {hint}")
    return value


def assert_no_service_role() -> None:
    """service_role 키가 환경에 있으면 앱을 멈춘다.

    이 키는 RLS를 우회한다. 실수로 넣어두면 '앱이 RLS를 우회할 수 없다'는
    이 프로젝트의 보안 전제가 조용히 깨지므로, 코드가 거부한다.
    """
    offenders = [name for name in os.environ if "SERVICE_ROLE" in name.upper()]
    if offenders:
        raise RuntimeError(
            f"{', '.join(offenders)} 가 환경에 있습니다. "
            "이 키는 RLS를 우회하므로 이 앱은 쓰지 않습니다. .env와 셸 환경에서 지우세요."
        )


def get_supabase_url() -> str:
    return _require(
        "SUPABASE_URL",
        "대시보드 > Project Settings > API 의 Project URL 을 넣으세요.",
    )


def get_supabase_anon_key() -> str:
    """anon(공개) 키. service_role·JWT Secret이면 거부한다."""
    from todoapp.keycheck import classify_key

    load_dotenv(PROJECT_ROOT / ".env")
    assert_no_service_role()
    key = _require(
        "SUPABASE_ANON_KEY",
        "대시보드 > Project Settings > API Keys 의 anon / publishable 키를 넣으세요.",
    )
    name, safe, note = classify_key(key)
    if not safe:
        # 키 값 자체는 메시지에 담지 않는다
        raise RuntimeError(f"SUPABASE_ANON_KEY 가 안전하지 않습니다 — {name}. {note}")
    return key


DEFAULT_PORT = 5001


def get_port() -> int:
    """웹 서버 포트. .env의 PORT, 없으면 5001.

    5000을 기본값으로 쓰지 않는 이유: macOS Monterey부터 AirPlay 수신기가
    5000번을 상시 점유한다. 우리 앱과 자리를 나눠 갖게 되어 localhost로
    들어가면 AirPlay가 403을 돌려주고, 127.0.0.1로 들어가야만 앱에 닿는다.
    Flask의 기본 포트가 5000이라 무심코 쓰기 쉬운 함정이다.
    """
    load_dotenv(PROJECT_ROOT / ".env")
    raw = os.getenv("PORT", "").strip()
    if not raw:
        return DEFAULT_PORT
    try:
        port = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"PORT 값이 숫자가 아닙니다: {raw!r}") from exc
    if not (1 <= port <= 65535):
        raise RuntimeError(f"PORT는 1~65535 사이여야 합니다: {port}")
    return port
