"""라우트. 변경 요청은 모두 POST + 리다이렉트(PRG)로 처리한다."""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from todoapp import auth_flow
from todoapp.auth_flow import NotLoggedIn
from todoapp.models import PRIORITY_LABELS, ValidationError
from todoapp.service import SCOPE_LABELS, SCOPES, TodoNotFound
from todoapp.supabase_client import AuthError

bp = Blueprint("todos", __name__)

# 로그인하지 않아도 열 수 있는 화면
_PUBLIC_ENDPOINTS = {"todos.login", "todos.signup", "static"}


def _web():
    """순환 import를 피하기 위해 호출 시점에 가져온다."""
    from todoapp import web

    return web


def _service():
    return _web().get_service()


@bp.before_request
def require_login():
    """Supabase 저장소인데 로그인하지 않았으면 로그인 화면으로 보낸다.

    SQLite 저장소는 계정 개념이 없으므로 통과한다.
    """
    web = _web()
    if not web.requires_login():
        return None
    if request.endpoint in _PUBLIC_ENDPOINTS:
        return None
    if web.load_tokens() is None:
        return redirect(url_for(".login", next=request.full_path))
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    return _auth_screen("login", "로그인", auth_flow.login)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    return _auth_screen("signup", "회원가입", auth_flow.signup)


def _auth_screen(mode: str, title: str, action):
    """로그인·회원가입 화면. 두 흐름이 폼과 오류 처리를 공유한다."""
    web = _web()
    if not web.requires_login():
        # SQLite 저장소에서는 로그인 화면이 의미가 없다
        return redirect(url_for(".index"))
    if request.method == "GET":
        return render_template("auth.html", mode=mode, title=title)
    try:
        tokens = action(
            request.form.get("email", ""), request.form.get("password", "")
        )
    except (AuthError, NotLoggedIn, RuntimeError) as exc:
        flash(str(exc))
        # 이메일만 되살린다. 비밀번호는 화면에 되돌려주지 않는다.
        return render_template(
            "auth.html",
            mode=mode,
            title=title,
            email=request.form.get("email", ""),
        )
    web.save_tokens(tokens)
    return redirect(url_for(".index"))


@bp.post("/logout")
def logout():
    auth_flow.revoke()
    _web().clear_tokens()
    flash("로그아웃했습니다.")
    return redirect(url_for(".login"))


def _current_filters() -> dict[str, str]:
    """지금 보고 있는 필터. POST 후 같은 화면으로 돌아가기 위해 쓴다."""
    source = request.form if request.method == "POST" else request.args
    filters: dict[str, str] = {}
    for key in ("scope", "tag", "q"):
        value = (source.get(key) or "").strip()
        if value:
            filters[key] = value
    return filters


@bp.get("/")
def index():
    filters = _current_filters()
    scope = filters.get("scope", "all")
    if scope not in SCOPES:
        abort(400, description=f"알 수 없는 범위입니다: {scope}")
    service = _service()
    todos = service.list(scope, tag=filters.get("tag"), keyword=filters.get("q"))
    return render_template(
        "index.html",
        todos=todos,
        all_tags=service.all_tags(),
        summary=service.summary(),
        today=service.today(),
        scope=scope,
        scopes=SCOPES,
        scope_labels=SCOPE_LABELS,
        priority_labels=PRIORITY_LABELS,
        active_tag=filters.get("tag", ""),
        query=filters.get("q", ""),
        account=_account_label(),
    )


def _account_label() -> str | None:
    """화면 아래에 보여줄 계정 표시. 토큰은 담지 않는다."""
    web = _web()
    if not web.requires_login():
        return None
    tokens = web.load_tokens()
    return (tokens.email or "(이메일 미확인)") if tokens else None


@bp.post("/todos")
def create():
    # 리다이렉트는 성공·실패 모두 한다(PRG). 실패는 flash로 알린다.
    filters = _current_filters()
    try:
        _service().add(
            request.form.get("title", ""),
            notes=request.form.get("notes") or None,
            due=request.form.get("due_date") or None,
            priority=request.form.get("priority") or None,
            tags=request.form.get("tags") or None,
        )
    except ValidationError as exc:
        flash(str(exc))
    return redirect(url_for(".index", **filters))


@bp.post("/todos/<int:todo_id>/toggle")
def toggle(todo_id: int):
    filters = _current_filters()
    try:
        _service().toggle(todo_id)
    except TodoNotFound:
        abort(404)
    return redirect(url_for(".index", **filters))


@bp.post("/todos/<int:todo_id>/delete")
def delete(todo_id: int):
    filters = _current_filters()
    try:
        _service().delete(todo_id)
    except TodoNotFound:
        abort(404)
    return redirect(url_for(".index", **filters))
