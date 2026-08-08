"""Where context-bundle's own global state lives on disk.

Deliberately independent of the user-chosen bundle *destination* -- this is
internal bookkeeping (config + per-session pointers), not bundle content.
Overridable via CONTEXT_BUNDLES_HOME for testing.
"""

import os


def home_dir():
    override = os.environ.get("CONTEXT_BUNDLES_HOME")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".context_bundles")


def config_path():
    return os.path.join(home_dir(), "config.json")


def state_dir():
    return os.path.join(home_dir(), "state")


def session_pointer_path(session_id):
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
    return os.path.join(state_dir(), safe_id + ".json")
