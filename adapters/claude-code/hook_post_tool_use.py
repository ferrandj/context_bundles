#!/usr/bin/env python3
"""Claude Code PostToolUse hook: append the operation for every tool call.

Matcher is "*" (see hooks.json) -- this fires for every tool, and
tool_operation_map.map_tool() always returns a bucket ("other" as the
fallback), so no tool call is silently dropped from the bundle.
"""

from _shared import emit, read_stdin_json

from core import bundle_config, bundle_writer, session_state
from tool_operation_map import map_tool


def main():
    payload = read_stdin_json()
    session_id = payload.get("session_id") or "unknown-session"
    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}

    try:
        config = bundle_config.load_config()
        if not config.get("enabled") or not tool_name:
            emit()
            return
        bundle_path = session_state.get_active_bundle(session_id)
        if not bundle_path:
            emit()
            return
        meta = bundle_writer.read_session_meta(bundle_path) or {}
        root_path = meta.get("root_path")
        operation, details = map_tool(tool_name, tool_input, root_path)
        bundle_writer.append_operation(bundle_path, operation, details)
    except Exception:
        pass

    emit()


if __name__ == "__main__":
    main()
