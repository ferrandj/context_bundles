"""Shared helpers for the Claude Code adapter's hook scripts.

Each hook script is invoked as a short-lived subprocess by Claude Code with
a JSON payload on stdin (see references/patterns.md read during design:
common fields session_id/transcript_path/cwd/hook_event_name, plus
event-specific fields). These helpers centralize: reading that payload,
locating core/, and failing *open* -- a bug here must never block the
user's real work, so every hook script catches broadly and exits 0.
"""

import json
import os
import sys

_ADAPTER_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_ADAPTER_DIR))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def read_stdin_json():
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def emit(output=None):
    """Write a hook output object (or nothing) and exit 0."""
    if output:
        sys.stdout.write(json.dumps(output))
    sys.exit(0)


def current_username():
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
