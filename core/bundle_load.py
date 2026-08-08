#!/usr/bin/env python3
"""Static CLI: turn a bundle into a replay plan.

    bundle_load.py <bundle-id|latest> [--dir <path>]

Prints a single JSON object to stdout:

    {
      "bundle_id": ...,
      "session_meta": {...} | null,
      "prompts": [{"text": ...}, ...],
      "context_operations": [{"operation": ..., "details": {...}, "stale": bool}, ...],
      "stats": {"total_lines": N, "malformed": N, "deduped_from": N, "excluded": N}
    }

This performs ONLY parsing, deduplication, filtering, and a best-effort
staleness check -- it never re-executes a read, fetch, or search itself.
That step requires an actual agent (see adapters/*/README or SKILL.md),
because only the agent can populate its own context window.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.bundle_config import load_config
from core.bundle_format import REPLAYABLE_OPERATIONS
from core.bundle_list import list_bundles
from core.bundle_writer import read_bundle_lines


def resolve_bundle_path(bundle_id, destination):
    if not destination or not os.path.isdir(destination):
        raise FileNotFoundError("no destination configured or destination does not exist")
    if bundle_id == "latest":
        entries = list_bundles(destination)
        if not entries:
            raise FileNotFoundError("no bundles found in {}".format(destination))
        return entries[0]["path"], entries[0]["id"]
    candidate = os.path.join(destination, bundle_id + ".jsonl")
    if os.path.exists(candidate):
        return candidate, bundle_id
    candidate = os.path.join(destination, bundle_id)
    if os.path.exists(candidate):
        return candidate, bundle_id[: -len(".jsonl")] if bundle_id.endswith(".jsonl") else bundle_id
    raise FileNotFoundError("no bundle found matching id {!r} in {}".format(bundle_id, destination))


def _details_key(details):
    return json.dumps(details, sort_keys=True)


def build_replay_plan(bundle_path, bundle_id):
    session_meta = None
    total_lines = 0
    malformed = 0
    ordered_ops = []  # list of (operation, details)
    seen = set()
    deduped_from = 0
    excluded = 0

    for line_no, obj, _raw in read_bundle_lines(bundle_path):
        total_lines += 1
        if line_no == 1:
            session_meta = obj
            if obj is None:
                malformed += 1
            continue
        if obj is None:
            malformed += 1
            continue
        operation = obj.get("operation")
        details = obj.get("details", {})
        if operation not in REPLAYABLE_OPERATIONS:
            excluded += 1
            continue
        key = (operation, _details_key(details))
        if key in seen:
            deduped_from += 1
            continue
        seen.add(key)
        ordered_ops.append((operation, details))

    prompts = []
    context_operations = []
    root_path = (session_meta or {}).get("root_path")
    for operation, details in ordered_ops:
        if operation == "prompt":
            prompts.append({"text": details.get("text", "")})
            continue
        entry = {"operation": operation, "details": details}
        if operation in ("read", "glob") and root_path:
            path = details.get("path")
            if path is not None:
                candidate = path if os.path.isabs(path) else os.path.join(root_path, path)
                entry["stale"] = not os.path.exists(candidate)
        context_operations.append(entry)

    return {
        "bundle_id": bundle_id,
        "session_meta": session_meta,
        "prompts": prompts,
        "context_operations": context_operations,
        "stats": {
            "total_lines": total_lines,
            "malformed": malformed,
            "deduped_from": deduped_from,
            "excluded": excluded,
        },
    }


def main(argv):
    if not argv:
        print("usage: bundle_load.py <bundle-id|latest> [--dir <path>]", file=sys.stderr)
        return 2
    bundle_id = argv[0]
    destination = None
    if len(argv) >= 3 and argv[1] == "--dir":
        destination = argv[2]
    else:
        destination = load_config()["destination"]

    try:
        bundle_path, resolved_id = resolve_bundle_path(bundle_id, destination)
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    plan = build_replay_plan(bundle_path, resolved_id)
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
