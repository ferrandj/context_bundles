#!/usr/bin/env python3
"""Claude Code SessionStart hook.

Behavior:
  - disabled            -> do nothing.
  - enabled, no dest     -> emit a systemMessage asking the agent to collect
                            a destination from the user and persist it via
                            `core/bundle_config.py set-destination`. Does not
                            create a bundle file yet (nothing to record into).
  - enabled, dest set    -> create <destination>/<new filename>.jsonl with the
                            session-meta line, and point this session_id at it.

Always exits 0. A failure here (bad permissions, disk full, whatever) must
never block or slow down the user's actual session.
"""

import os

from _shared import current_username, emit, read_stdin_json

from core import bundle_config, bundle_writer, session_state


def main():
    payload = read_stdin_json()
    session_id = payload.get("session_id") or "unknown-session"
    cwd = payload.get("cwd") or os.getcwd()

    try:
        session_state.sweep_stale_pointers()
    except Exception:
        pass

    try:
        config = bundle_config.load_config()
    except Exception:
        emit()
        return

    if not config.get("enabled"):
        emit()
        return

    destination = config.get("destination")
    if not destination:
        emit({
            "systemMessage": (
                "context-bundle is enabled but no destination folder is configured yet. "
                "Ask the user (via AskUserQuestion) where they want session bundles stored, "
                "then run `python3 core/bundle_config.py set-destination <path>` in the "
                "context_bundles repo to save it. No bundle will be recorded for this "
                "session until that's done."
            )
        })
        return

    try:
        filename = bundle_writer.new_bundle_filename()
        bundle_path = os.path.join(destination, filename)
        bundle_writer.write_session_meta(
            bundle_path,
            username=current_username(),
            root_path=cwd,
            session_id=session_id,
        )
        session_state.set_active_bundle(session_id, bundle_path)
    except Exception:
        # Fail open: recording is best-effort, never blocks the session.
        pass

    emit()


if __name__ == "__main__":
    main()
