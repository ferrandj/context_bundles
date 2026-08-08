#!/usr/bin/env python3
"""Static CLI: list bundles found in the configured destination.

    bundle_list.py                # uses configured destination
    bundle_list.py --dir <path>   # override, e.g. for tests

Prints one JSON object per line (JSONL) to stdout, newest first, each with
the bundle's id (filename without .jsonl), path, size, line_count, and the
parsed session-meta line (username/root_path/session_id/started_at) when
available. Never raises on a malformed bundle -- reports it with an "error"
field instead so one bad file doesn't hide the rest.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.bundle_config import load_config
from core.bundle_format import FILENAME_RE


def _read_meta(bundle_path):
    try:
        with open(bundle_path, "r", encoding="utf-8") as fh:
            first_line = fh.readline()
            line_count = 1 if first_line.strip() else 0
            for _ in fh:
                line_count += 1
    except OSError as exc:
        return None, 0, str(exc)
    if not first_line.strip():
        return None, line_count, "empty file"
    try:
        meta = json.loads(first_line)
    except json.JSONDecodeError as exc:
        return None, line_count, "malformed meta line: {}".format(exc)
    return meta, line_count, None


def list_bundles(destination):
    if not destination or not os.path.isdir(destination):
        return []
    entries = []
    for name in os.listdir(destination):
        if not name.endswith(".jsonl"):
            continue
        full = os.path.join(destination, name)
        meta, line_count, error = _read_meta(full)
        entries.append({
            "id": name[: -len(".jsonl")],
            "filename": name,
            "path": full,
            "size_bytes": os.path.getsize(full),
            "line_count": line_count,
            "well_formed_name": bool(FILENAME_RE.match(name)),
            "session_meta": meta,
            "error": error,
        })
    entries.sort(key=lambda e: e["filename"], reverse=True)
    return entries


def main(argv):
    destination = None
    if len(argv) >= 2 and argv[0] == "--dir":
        destination = argv[1]
    else:
        destination = load_config()["destination"]

    for entry in list_bundles(destination):
        print(json.dumps(entry))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
