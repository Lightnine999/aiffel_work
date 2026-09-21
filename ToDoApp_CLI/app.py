#!/usr/bin/env python3
"""`python3 app.py` 로 웹 화면 띄우기.

로컬 전용이다. host를 0.0.0.0으로 바꾸지 말 것 — CSRF 보호가 없다.
포트는 .env의 PORT로 바꿀 수 있다 (기본 5001).
"""

from todoapp.config import get_port
from todoapp.web import create_app

if __name__ == "__main__":
    port = get_port()
    print(f"  → http://127.0.0.1:{port}  /  http://localhost:{port}")
    create_app().run(host="127.0.0.1", port=port, debug=True)
