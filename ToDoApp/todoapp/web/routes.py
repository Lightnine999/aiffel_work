"""라우트. 변경 요청은 모두 POST + 리다이렉트(PRG)로 처리한다."""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from todoapp.models import PRIORITY_LABELS, ValidationError
from todoapp.service import SCOPE_LABELS, SCOPES, TodoNotFound

bp = Blueprint("todos", __name__)


def _service():
    """순환 import를 피하기 위해 호출 시점에 가져온다."""
    from todoapp.web import get_service

    return get_service()


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
    )


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
