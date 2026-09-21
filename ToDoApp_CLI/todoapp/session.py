"""CLI 로그인 세션 저장소.

토큰은 비밀값이다. 파일 권한 0600(소유자만 읽기·쓰기), 디렉터리 0700으로 만든다.
`os.open`으로 권한을 지정해 생성하는 이유: 먼저 만들고 chmod하면 그 사이에
다른 프로세스가 읽을 수 있는 짧은 틈이 생긴다.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

SESSION_DIR = Path.home() / ".config" / "todoapp"
SESSION_PATH = SESSION_DIR / "session.json"

_FILE_MODE = 0o600
_DIR_MODE = 0o700


@dataclass(frozen=True, slots=True)
class Tokens:
    access_token: str
    refresh_token: str
    email: str | None = None
    user_id: str | None = None


def save(tokens: Tokens, path: Path | None = None) -> Path:
    target = path or SESSION_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(target.parent, _DIR_MODE)
    payload = json.dumps(asdict(tokens), ensure_ascii=False, indent=2)
    # 기존 파일이 넉넉한 권한으로 남아 있을 수 있으니 지우고 새로 만든다
    if target.exists():
        target.unlink()
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _FILE_MODE)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload + "\n")
    return target


def load(path: Path | None = None) -> Tokens | None:
    target = path or SESSION_PATH
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    if not access or not refresh:
        return None
    return Tokens(
        access_token=access,
        refresh_token=refresh,
        email=data.get("email"),
        user_id=data.get("user_id"),
    )


def clear(path: Path | None = None) -> bool:
    target = path or SESSION_PATH
    if target.is_file():
        target.unlink()
        return True
    return False
