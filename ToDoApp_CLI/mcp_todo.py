#!/usr/bin/env python3
"""MCP 서버 진입점. `python3 mcp_todo.py` 로 stdio 서버를 띄운다."""

from todoapp.mcp_server import main

if __name__ == "__main__":
    raise SystemExit(main())
