"""Static, dependency-free writer for context-bundle JSONL files.

Every function here is a pure/deterministic operation on the filesystem --
no LLM calls, no network. Adapters call into this module from their event
hooks.
"""

import datetime
import json
import os
import uuid

from core.bundle_format import SCHEMA_VERSION


def new_bundle_filename(now=None):
    """Return a fresh ``YY-MM-DD_HH-MM-SS_<uuid4>.jsonl`` filename."""
    now = now or datetime.datetime.now()
    return "{}_{}.jsonl".format(now.strftime("%y-%m-%d_%H-%M-%S"), uuid.uuid4())


def relativize(path, root_path):
    """Return (stored_path, outside_root) for a path relative to root_path.

    If ``path`` is under ``root_path`` the relative form is returned with
    ``outside_root=False``. Otherwise the absolute form is returned with
    ``outside_root=True`` -- the bundle format has no way to express a path
    outside the session root as a relative path, so we say so explicitly
    instead of guessing.
    """
    abs_path = os.path.abspath(path)
    abs_root = os.path.abspath(root_path)
    try:
        rel = os.path.relpath(abs_path, abs_root)
    except ValueError:
        # Different drives on Windows, etc.
        return abs_path, True
    if rel.startswith(".."):
        return abs_path, True
    return rel, False


def _append_line(bundle_path, obj):
    """Append one JSON object as a single line, atomically (POSIX O_APPEND)."""
    line = (json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    os.makedirs(os.path.dirname(bundle_path), exist_ok=True)
    fd = os.open(bundle_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def write_session_meta(bundle_path, username, root_path, session_id, started_at=None):
    """Write the mandatory first line of a bundle. No-op if the file already
    has content (idempotent against duplicate SessionStart firings)."""
    if os.path.exists(bundle_path) and os.path.getsize(bundle_path) > 0:
        return False
    started_at = started_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    meta = {
        "username": username,
        "root_path": root_path,
        "session_id": session_id,
        "started_at": started_at,
        "schema_version": SCHEMA_VERSION,
    }
    _append_line(bundle_path, meta)
    return True


def append_operation(bundle_path, operation, details, ts=None):
    """Append one operation line."""
    ts = ts or datetime.datetime.now(datetime.timezone.utc).isoformat()
    _append_line(bundle_path, {"ts": ts, "operation": operation, "details": details})


def read_session_meta(bundle_path):
    """Read and parse just the first line of a bundle, or None."""
    try:
        with open(bundle_path, "r", encoding="utf-8") as fh:
            first_line = fh.readline()
    except OSError:
        return None
    if not first_line.strip():
        return None
    try:
        return json.loads(first_line)
    except json.JSONDecodeError:
        return None


def read_bundle_lines(bundle_path):
    """Yield (line_number, parsed_obj_or_None, raw_line) for every line.

    parsed_obj is None for lines that fail to JSON-decode -- callers decide
    whether to skip/count them rather than the reader raising.
    """
    with open(bundle_path, "r", encoding="utf-8") as fh:
        for i, raw in enumerate(fh, start=1):
            raw = raw.rstrip("\n")
            if not raw.strip():
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                obj = None
            yield i, obj, raw
