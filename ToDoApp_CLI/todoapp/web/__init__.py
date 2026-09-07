"""Flask 앱 팩토리.

저장소는 설정(STORAGE)이 정한다. 이 모듈은 어떤 저장소인지 모른다 —
build_store()가 유일한 분기점이다.

세션 보관: Supabase 토큰을 Flask 세션(서명된 쿠키)에 담는다. 그래서
FLASK_SECRET_KEY가 필요하다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from flask import Flask, current_app, g, session

from todoapp.config import get_db_path, get_secret_key, get_storage_backend
from todoapp.service import TodoService
from todoapp.session import Tokens
from todoapp.stores import build_store

_STORE_KEY = "_todoapp_store"
_SESSION_FIELD = "supabase_tokens"


def create_app(
    *,
    db_path: str | Path | None = None,
    secret_key: str | None = None,
    today: Callable[[], str] | None = None,
    backend: str | None = None,
) -> Flask:
    app = Flask(__name__)
    # 비밀키를 먼저 확정한다. 없으면 DB를 건드리기 전에 멈춘다.
    app.secret_key = secret_key or get_secret_key()
    app.config["TODOAPP_TODAY"] = today
    # db_path를 명시하면 sqlite로 본다. SQLite 파일 경로를 주면서 클라우드를
    # 원하는 것은 모순이다. backend를 직접 주면 그게 이긴다.
    if backend is None and db_path is not None:
        backend = "sqlite"
    app.config["TODOAPP_BACKEND"] = (backend or get_storage_backend()).lower()

    if app.config["TODOAPP_BACKEND"] == "sqlite":
        # 로컬 파일은 시작할 때 한 번만 스키마를 적용한다.
        app.config["TODOAPP_DB_PATH"] = Path(db_path) if db_path else get_db_path()
        bootstrap = build_store(
            "sqlite", db_path=app.config["TODOAPP_DB_PATH"], init_schema=True
        )
        bootstrap.close()

    from todoapp.web.routes import bp

    app.register_blueprint(bp)
    app.teardown_appcontext(_close_store)
    return app


# ---------------------------------------------------------------- 세션


def save_tokens(tokens: Tokens) -> None:
    """토큰을 Flask 세션에 담는다. 서명된 쿠키이므로 위조되지 않는다."""
    session[_SESSION_FIELD] = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "email": tokens.email,
        "user_id": tokens.user_id,
    }


def load_tokens() -> Tokens | None:
    data = session.get(_SESSION_FIELD)
    if not data or not data.get("access_token"):
        return None
    return Tokens(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", ""),
        email=data.get("email"),
        user_id=data.get("user_id"),
    )


def clear_tokens() -> None:
    session.pop(_SESSION_FIELD, None)


def requires_login() -> bool:
    """이 저장소가 로그인을 요구하는가."""
    return current_app.config["TODOAPP_BACKEND"] != "sqlite"


# ---------------------------------------------------------------- 저장소


def _build_store_for_request():
    backend = current_app.config["TODOAPP_BACKEND"]
    if backend == "sqlite":
        # 요청마다 저장소를 새로 연다. sqlite3 커넥션은 기본적으로 만든
        # 스레드에서만 쓸 수 있어서 앱 전역에 하나를 두면 Flask와 충돌한다.
        # 스키마는 시작할 때 이미 적용했으므로 건너뛴다.
        return build_store(
            "sqlite",
            db_path=current_app.config["TODOAPP_DB_PATH"],
            init_schema=False,
        )
    tokens = load_tokens()
    store = build_store("supabase", tokens=tokens)
    fresh = getattr(store, "tokens", None)
    if fresh is not None and fresh != tokens:
        save_tokens(fresh)  # 갱신된 토큰을 쿠키에도 반영
    return store


def get_store():
    store = getattr(g, _STORE_KEY, None)
    if store is None:
        store = _build_store_for_request()
        setattr(g, _STORE_KEY, store)
    return store


def _close_store(exception: BaseException | None = None) -> None:
    store = getattr(g, _STORE_KEY, None)
    if store is not None:
        close = getattr(store, "close", None)
        if callable(close):
            close()
        setattr(g, _STORE_KEY, None)


def get_service() -> TodoService:
    """이 요청에 묶인 서비스. 요청 컨텍스트 안에서만 부를 수 있다."""
    today = current_app.config.get("TODOAPP_TODAY")
    store = get_store()
    return TodoService(store, today=today) if today else TodoService(store)
