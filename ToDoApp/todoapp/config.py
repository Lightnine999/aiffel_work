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
