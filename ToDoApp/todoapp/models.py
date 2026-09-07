"""도메인 값 객체와 입력 정규화·검증.

이 모듈은 DB를 모른다. 순수 함수만 있으므로 테스트가 가장 싸다.
'정규화'와 '검증'을 한 함수에 묶은 이유: 입력을 받는 지점이 CLI·웹 둘이라,
두 곳에서 각자 다듬으면 규칙이 갈라진다. 진입점 하나로 강제한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

PRIORITY_HIGH = 1
PRIORITY_NORMAL = 2
PRIORITY_LOW = 3

PRIORITY_NAMES: dict[str, int] = {
    "high": PRIORITY_HIGH,
    "normal": PRIORITY_NORMAL,
    "low": PRIORITY_LOW,
}
PRIORITY_LABELS: dict[int, str] = {
    PRIORITY_HIGH: "높음",
    PRIORITY_NORMAL: "보통",
    PRIORITY_LOW: "낮음",
}

DEFAULT_TAG_COLOR = "#888880"
MAX_TITLE_LENGTH = 200
MAX_TAG_LENGTH = 30

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_WHITESPACE_RUN_RE = re.compile(r"\s+")


class _Unset:
    """'값을 주지 않았다'를 뜻하는 센티널. None(값을 비워라)과 구분하려고 쓴다."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET = _Unset()


def is_set(value: object) -> bool:
    """UNSET 센티널이 아닌 '실제로 주어진 값'인지 판정한다.

    상위 계층이 isinstance(x, _Unset)처럼 비공개 이름을 쓰지 않게 하려고 노출한다.
    """
    return not isinstance(value, _Unset)


class ValidationError(ValueError):
    """사용자 입력이 규칙을 어겼을 때. CLI·웹이 이걸 잡아 안내 문구로 바꾼다."""


@dataclass(frozen=True, slots=True)
class Tag:
    id: int | None
    name: str
    color: str = DEFAULT_TAG_COLOR


@dataclass(frozen=True, slots=True)
class Todo:
    id: int | None
    title: str
    notes: str | None = None
    is_done: bool = False
    due_date: str | None = None
    priority: int = PRIORITY_NORMAL
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
    tags: tuple[Tag, ...] = field(default=())


def normalize_title(raw: str | None) -> str:
    """제목을 다듬는다. 앞뒤 공백 제거 + 내부 연속 공백을 하나로."""
    if raw is None:
        raise ValidationError("제목을 입력하세요.")
    title = _WHITESPACE_RUN_RE.sub(" ", str(raw)).strip()
    if not title:
        raise ValidationError("제목을 입력하세요.")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValidationError(f"제목은 {MAX_TITLE_LENGTH}자를 넘을 수 없습니다.")
    return title


def normalize_due_date(raw: str | None) -> str | None:
    """마감일을 'YYYY-MM-DD'로 확정한다. 빈 값은 None(마감일 없음)."""
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    # 형식 검사를 먼저 한다. date.fromisoformat은 Python 3.11+에서
    # '20260904' 같은 하이픈 없는 형식도 받아주기 때문이다.
    if not _ISO_DATE_RE.match(value):
        raise ValidationError(f"마감일은 'YYYY-MM-DD' 형식이어야 합니다: {raw!r}")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"존재하지 않는 날짜입니다: {value}") from exc
    return value


def normalize_tag_name(raw: str | None) -> str:
    if raw is None:
        raise ValidationError("태그 이름을 입력하세요.")
    name = _WHITESPACE_RUN_RE.sub(" ", str(raw)).strip()
    if not name:
        raise ValidationError("태그 이름을 입력하세요.")
    if "," in name:
        raise ValidationError("태그 이름에 쉼표를 쓸 수 없습니다.")
    if len(name) > MAX_TAG_LENGTH:
        raise ValidationError(f"태그는 {MAX_TAG_LENGTH}자를 넘을 수 없습니다.")
    return name


def parse_tag_list(raw: str | Iterable[str] | None) -> tuple[str, ...]:
    """'공부, 집안일' 또는 ['공부','집안일']을 정규화된 튜플로.

    중복은 첫 등장만 남긴다. DB의 tags.name이 COLLATE NOCASE라
    대소문자만 다른 이름은 같은 태그로 취급한다.
    """
    if raw is None:
        return ()
    parts = raw.split(",") if isinstance(raw, str) else list(raw)
    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if part is None or not str(part).strip():
            continue
        name = normalize_tag_name(part)
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(name)
    return tuple(result)


def normalize_color(raw: str | None) -> str:
    if raw is None or not str(raw).strip():
        return DEFAULT_TAG_COLOR
    color = str(raw).strip()
    if not _HEX_COLOR_RE.match(color):
        raise ValidationError(f"색상은 '#RRGGBB' 형식이어야 합니다: {raw!r}")
    return color.upper()


def normalize_priority(raw: int | str | None) -> int:
    if raw is None:
        return PRIORITY_NORMAL
    if isinstance(raw, bool):  # bool은 int의 하위형이라 먼저 걸러낸다
        raise ValidationError(f"알 수 없는 우선순위입니다: {raw!r}")
    if isinstance(raw, int):
        value = raw
    else:
        text = str(raw).strip().lower()
        if text in PRIORITY_NAMES:
            return PRIORITY_NAMES[text]
        try:
            value = int(text)
        except ValueError as exc:
            raise ValidationError(f"알 수 없는 우선순위입니다: {raw!r}") from exc
    if value not in PRIORITY_LABELS:
        raise ValidationError("우선순위는 1(높음)·2(보통)·3(낮음) 중 하나여야 합니다.")
    return value
