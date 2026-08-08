"""WSGI application powering the context-bundle local GUI.

Stdlib only (no Flask/Django/etc.) -- consistent with the rest of this
project: zero new dependencies, runs with nothing but `python3`, and is
directly callable in tests without spinning up a real socket. All the
actual logic still lives in `core/` and `adapters/claude-code/`; this file
is just a thin JSON API + static file server on top of it.

Routes:
  GET  /api/status          -> {enabled, destination, bundle_count}
  GET  /api/hooks-status    -> which Claude Code hook events are installed
  POST /api/config          -> {"destination": "<path>"} set destination
  POST /api/enable          -> enable config + install Claude Code hooks
  POST /api/disable         -> uninstall hooks + disable config
  GET  /api/bundles         -> {"bundles": [...]} (newest first)
  GET  /api/bundles/<id>    -> replay plan for one bundle ("latest" allowed)
  GET  /                    -> static/index.html
  GET  /<anything else>     -> static/<anything else>
"""

import json
import mimetypes
import os
import re
import sys

_GUI_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_GUI_DIR)
_ADAPTER_DIR = os.path.join(_REPO_ROOT, "adapters", "claude-code")
for p in (_REPO_ROOT, _ADAPTER_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from core import bundle_config, bundle_list, bundle_load  # noqa: E402
import install as claude_install  # noqa: E402  (adapters/claude-code/install.py)

STATIC_DIR = os.path.join(_GUI_DIR, "static")

# No slashes/backslashes allowed -> resolve_bundle_path can only ever land
# on a plain filename inside the configured destination, never traverse
# out of it. "latest" is the one non-matching id we special-case below.
_BUNDLE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_BUNDLE_PATH_RE = re.compile(r"^/api/bundles/([^/]+)$")


def _settings_path():
    return os.environ.get("CONTEXT_BUNDLES_SETTINGS_PATH") or claude_install.default_settings_path()


def _json_bytes(payload):
    return json.dumps(payload).encode("utf-8")


def _respond(start_response, status, payload):
    body = _json_bytes(payload)
    start_response(status, [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
    ])
    return [body]


def _read_json_body(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    if length <= 0:
        return {}
    raw = environ["wsgi.input"].read(length)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _serve_static(start_response, path):
    rel = (path or "/").lstrip("/")
    if rel == "":
        rel = "index.html"
    requested = os.path.normpath(os.path.join(STATIC_DIR, rel))
    static_root = os.path.normpath(STATIC_DIR)
    if requested != static_root and not requested.startswith(static_root + os.sep):
        return _respond(start_response, "403 Forbidden", {"error": "forbidden"})
    if not os.path.isfile(requested):
        return _respond(start_response, "404 Not Found", {"error": "not found"})
    content_type, _ = mimetypes.guess_type(requested)
    with open(requested, "rb") as fh:
        body = fh.read()
    start_response("200 OK", [
        ("Content-Type", content_type or "application/octet-stream"),
        ("Content-Length", str(len(body))),
    ])
    return [body]


def _status_payload():
    config = bundle_config.load_config()
    return {
        "enabled": config["enabled"],
        "destination": config["destination"],
        "bundle_count": bundle_config._count_bundles(config["destination"]),
    }


def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")

    try:
        if path == "/api/status" and method == "GET":
            return _respond(start_response, "200 OK", _status_payload())

        if path == "/api/hooks-status" and method == "GET":
            return _respond(start_response, "200 OK", claude_install.status(_settings_path()))

        if path == "/api/config" and method == "POST":
            body = _read_json_body(environ)
            destination = (body.get("destination") or "").strip()
            if not destination:
                return _respond(start_response, "400 Bad Request", {"error": "destination is required"})
            bundle_config.set_destination(destination)
            return _respond(start_response, "200 OK", _status_payload())

        if path == "/api/enable" and method == "POST":
            bundle_config.set_enabled(True)
            claude_install.enable(_settings_path())
            return _respond(start_response, "200 OK", _status_payload())

        if path == "/api/disable" and method == "POST":
            claude_install.disable(_settings_path())
            bundle_config.set_enabled(False)
            return _respond(start_response, "200 OK", _status_payload())

        if path == "/api/bundles" and method == "GET":
            destination = bundle_config.load_config()["destination"]
            return _respond(start_response, "200 OK", {"bundles": bundle_list.list_bundles(destination)})

        match = _BUNDLE_PATH_RE.match(path)
        if match and method == "GET":
            bundle_id = match.group(1)
            if bundle_id != "latest" and not _BUNDLE_ID_RE.match(bundle_id):
                return _respond(start_response, "400 Bad Request", {"error": "invalid bundle id"})
            destination = bundle_config.load_config()["destination"]
            try:
                bundle_path, resolved_id = bundle_load.resolve_bundle_path(bundle_id, destination)
            except FileNotFoundError as exc:
                return _respond(start_response, "404 Not Found", {"error": str(exc)})
            plan = bundle_load.build_replay_plan(bundle_path, resolved_id)
            return _respond(start_response, "200 OK", plan)

        if path.startswith("/api/"):
            return _respond(start_response, "404 Not Found", {"error": "unknown endpoint"})

        if method != "GET":
            return _respond(start_response, "405 Method Not Allowed", {"error": "method not allowed"})

        return _serve_static(start_response, path)

    except Exception as exc:  # noqa: BLE001 - never let the GUI crash the process
        return _respond(start_response, "500 Internal Server Error", {"error": str(exc)})
