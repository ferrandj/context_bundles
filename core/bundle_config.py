#!/usr/bin/env python3
"""Static CLI for reading/writing context-bundle's global config.

    bundle_config.py status
    bundle_config.py get-destination
    bundle_config.py set-destination <path>
    bundle_config.py enable
    bundle_config.py disable

Config lives at core.paths.config_path() (~/.context_bundles/config.json by
default, overridable via CONTEXT_BUNDLES_HOME for tests). Pure stdlib,
no LLM/agent involvement -- safe to call from any hook or script.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.paths import config_path, home_dir

DEFAULT_CONFIG = {"destination": None, "enabled": False}


def load_config():
    path = config_path()
    if not os.path.exists(path):
        return dict(DEFAULT_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def save_config(config):
    os.makedirs(home_dir(), exist_ok=True)
    path = config_path()
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp_path, path)


def set_destination(path):
    config = load_config()
    config["destination"] = os.path.abspath(os.path.expanduser(path))
    save_config(config)
    return config


def set_enabled(enabled):
    config = load_config()
    config["enabled"] = bool(enabled)
    save_config(config)
    return config


def _count_bundles(destination):
    if not destination or not os.path.isdir(destination):
        return 0
    return len([f for f in os.listdir(destination) if f.endswith(".jsonl")])


def main(argv):
    if not argv:
        print("usage: bundle_config.py <status|get-destination|set-destination|enable|disable>", file=sys.stderr)
        return 2
    cmd = argv[0]
    if cmd == "status":
        config = load_config()
        print(json.dumps({
            "enabled": config["enabled"],
            "destination": config["destination"],
            "bundle_count": _count_bundles(config["destination"]),
        }, indent=2))
        return 0
    if cmd == "get-destination":
        print(load_config()["destination"] or "")
        return 0
    if cmd == "set-destination":
        if len(argv) < 2:
            print("usage: bundle_config.py set-destination <path>", file=sys.stderr)
            return 2
        config = set_destination(argv[1])
        print(json.dumps(config, indent=2))
        return 0
    if cmd == "enable":
        config = set_enabled(True)
        print(json.dumps(config, indent=2))
        return 0
    if cmd == "disable":
        config = set_enabled(False)
        print(json.dumps(config, indent=2))
        return 0
    print("unknown command: {}".format(cmd), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
