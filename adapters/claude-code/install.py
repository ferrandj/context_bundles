#!/usr/bin/env python3
"""Idempotently add/remove context-bundle's hooks in a Claude Code
settings.json (top-level "hooks" -> {EventName: [...]}, matching the
format actually used by ~/.claude/settings.json).

    install.py enable  [--settings <path>]
    install.py disable [--settings <path>]
    install.py status  [--settings <path>]

Never touches any hook entry that isn't ours (identified by MARKER
appearing in its "command" string) -- other tools' hooks in the same file
are left exactly as they were.
"""

import json
import os
import sys

_ADAPTER_DIR = os.path.dirname(os.path.abspath(__file__))
MARKER = os.path.join("context_bundles", "adapters", "claude-code")


def default_settings_path():
    return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")


def load_template():
    tmpl_path = os.path.join(_ADAPTER_DIR, "hooks.json.tmpl")
    with open(tmpl_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    text = text.replace("__SCRIPT_DIR__", _ADAPTER_DIR)
    return json.loads(text)


def load_settings(settings_path):
    if not os.path.exists(settings_path):
        return {}
    with open(settings_path, "r", encoding="utf-8") as fh:
        content = fh.read()
    if not content.strip():
        return {}
    return json.loads(content)


def save_settings(settings_path, settings):
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    tmp_path = settings_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp_path, settings_path)


def _is_ours(hook_entry):
    return MARKER in hook_entry.get("command", "")


def _entry_is_ours(entry):
    return any(_is_ours(h) for h in entry.get("hooks", []))


def enable(settings_path):
    settings = load_settings(settings_path)
    hooks = settings.setdefault("hooks", {})
    template = load_template()

    for event_name, entries in template.items():
        existing = hooks.setdefault(event_name, [])
        already_installed = any(_entry_is_ours(e) for e in existing)
        if already_installed:
            continue
        existing.extend(entries)

    save_settings(settings_path, settings)
    return settings


def disable(settings_path):
    settings = load_settings(settings_path)
    hooks = settings.get("hooks", {})

    for event_name in list(hooks.keys()):
        entries = hooks[event_name]
        kept = []
        for entry in entries:
            filtered_hooks = [h for h in entry.get("hooks", []) if not _is_ours(h)]
            if not filtered_hooks:
                continue  # whole entry was ours (or now empty) -- drop it
            new_entry = dict(entry)
            new_entry["hooks"] = filtered_hooks
            kept.append(new_entry)
        if kept:
            hooks[event_name] = kept
        else:
            del hooks[event_name]

    if not hooks and "hooks" in settings:
        del settings["hooks"]

    save_settings(settings_path, settings)
    return settings


def status(settings_path):
    settings = load_settings(settings_path)
    hooks = settings.get("hooks", {})
    installed_events = [
        event for event, entries in hooks.items()
        if any(_entry_is_ours(e) for e in entries)
    ]
    return {"settings_path": settings_path, "installed_events": sorted(installed_events)}


def main(argv):
    if not argv:
        print("usage: install.py <enable|disable|status> [--settings <path>]", file=sys.stderr)
        return 2
    cmd = argv[0]
    settings_path = default_settings_path()
    if len(argv) >= 3 and argv[1] == "--settings":
        settings_path = argv[2]

    if cmd == "enable":
        print(json.dumps(enable(settings_path), indent=2))
    elif cmd == "disable":
        print(json.dumps(disable(settings_path), indent=2))
    elif cmd == "status":
        print(json.dumps(status(settings_path), indent=2))
    else:
        print("unknown command: {}".format(cmd), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
