#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook: append a "prompt" operation."""

from _shared import emit, read_stdin_json

from core import bundle_config, bundle_writer, session_state


def main():
    payload = read_stdin_json()
    session_id = payload.get("session_id") or "unknown-session"
    prompt_text = payload.get("user_prompt") or payload.get("prompt") or ""

    try:
        config = bundle_config.load_config()
        if not config.get("enabled"):
            emit()
            return
        bundle_path = session_state.get_active_bundle(session_id)
        if not bundle_path:
            emit()
            return
        bundle_writer.append_operation(bundle_path, "prompt", {"text": prompt_text})
    except Exception:
        pass

    emit()


if __name__ == "__main__":
    main()
