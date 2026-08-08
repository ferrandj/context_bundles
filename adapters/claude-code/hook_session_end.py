#!/usr/bin/env python3
"""Claude Code SessionEnd hook: drop this session's active-bundle pointer.

The bundle file itself is left untouched -- only the in-memory-equivalent
session_id -> path pointer in ~/.context_bundles/state/ is cleaned up.
"""

from _shared import emit, read_stdin_json

from core import session_state


def main():
    payload = read_stdin_json()
    session_id = payload.get("session_id") or "unknown-session"
    try:
        session_state.clear_active_bundle(session_id)
    except Exception:
        pass
    emit()


if __name__ == "__main__":
    main()
