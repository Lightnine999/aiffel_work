"""Flask 앱 팩토리. 요청마다 SQLite 커넥션을 새로 열고 닫는다."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable

from flask import Flask, current_app, g

from todoapp.config import get_db_path, get_secret_key
from todoapp.database import connect, initialize
from todoapp.service import TodoService

_CONN_KEY = "_todoapp_conn"


def create_app(
    *,
    db_path: str | Path | None = None,
    secret_key: str | None = None,
    today: Callable[[], str] | None = None,
) -> Flask:
    app = Flask(__name__)
    # 비밀키를 먼저 확정한다. 없으면 DB를 건드리기 전에 멈춘다.
    app.secret_key = secret_key or get_secret_key()
    app.config["TODOAPP_DB_PATH"] = Path(db_path) if db_path else get_db_path()
    app.config["TODOAPP_TODAY"] = today

    # 스키마는 시작할 때 한 번만 적용한다. 요청마다 하면 느려진다.
    bootstrap = connect(app.config["TODOAPP_DB_PATH"])
    try:
        initialize(bootstrap)
    finally:
        bootstrap.close()

    from todoapp.web.routes import bp

    app.register_blueprint(bp)
    app.teardown_appcontext(_close_connection)
    return app


def _get_connection() -> sqlite3.Connection:
    """이 요청의 커넥션. 없으면 만든다.

    앱 전역에 커넥션 하나를 두지 않는 이유: sqlite3 커넥션은 기본적으로
    만든 스레드에서만 쓸 수 있어서 Flask의 스레드 모델과 충돌한다.
    """
    conn = getattr(g, _CONN_KEY, None)
    if conn is None:
        conn = connect(current_app.config["TODOAPP_DB_PATH"])
        setattr(g, _CONN_KEY, conn)
    return conn


def _close_connection(exception: BaseException | None = None) -> None:
    conn = getattr(g, _CONN_KEY, None)
    if conn is not None:
        conn.close()
        setattr(g, _CONN_KEY, None)


def get_service() -> TodoService:
    """이 요청에 묶인 서비스. 요청 컨텍스트 안에서만 부를 수 있다."""
    today = current_app.config.get("TODOAPP_TODAY")
    conn = _get_connection()
    return TodoService(conn, today=today) if today else TodoService(conn)
