"""테스트 공용 fixture. 모든 테스트는 tmp_path 임시 DB만 쓴다."""
from __future__ import annotations

from pathlib import Path

import pytest

from todoapp.database import connect, initialize


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_todo.db"


@pytest.fixture
def conn(db_path: Path):
    connection = connect(db_path)
    initialize(connection)
    yield connection
    connection.close()
