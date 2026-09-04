#!/usr/bin/env python3
"""`python3 app.py` 로 웹 화면 띄우기.

로컬 전용이다. host를 0.0.0.0으로 바꾸지 말 것 — 로그인도 CSRF도 없다.
"""

from todoapp.web import create_app

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
