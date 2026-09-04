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
