"""Per-session pointer: which bundle file is the active session writing to.

Hooks are separate short-lived processes with no shared memory, so the
mapping from session_id -> bundle path has to be persisted somewhere
between a SessionStart hook firing and later PostToolUse hooks firing.
"""

import datetime
import json
import os

from core.paths import session_pointer_path, state_dir

STALE_AFTER_SECONDS = 24 * 60 * 60


def set_active_bundle(session_id, bundle_path):
    os.makedirs(state_dir(), exist_ok=True)
    payload = {
        "bundle_path": bundle_path,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with open(session_pointer_path(session_id), "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def get_active_bundle(session_id):
    path = session_pointer_path(session_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None
    return payload.get("bundle_path")


def clear_active_bundle(session_id):
    path = session_pointer_path(session_id)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def sweep_stale_pointers(now=None, max_age_seconds=STALE_AFTER_SECONDS):
    """Remove session pointer files older than max_age_seconds.

    Best-effort housekeeping run opportunistically from SessionStart so the
    state directory doesn't grow unbounded across crashed/killed sessions
    that never fired SessionEnd. Returns the number removed.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    d = state_dir()
    if not os.path.isdir(d):
        return 0
    removed = 0
    for name in os.listdir(d):
        if not name.endswith(".json"):
            continue
        full = os.path.join(d, name)
        try:
            with open(full, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            created_at = datetime.datetime.fromisoformat(payload["created_at"])
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            # Unreadable/corrupt pointer file -- treat as stale, remove it.
            os.remove(full)
            removed += 1
            continue
        if (now - created_at).total_seconds() > max_age_seconds:
            os.remove(full)
            removed += 1
    return removed
