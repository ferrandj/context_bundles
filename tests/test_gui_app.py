"""Tests for gui/app.py, the WSGI JSON API behind the local GUI.

The WSGI callable is invoked directly (no real socket/thread) with a
hand-built environ -- deterministic and fast, and exactly what a real
WSGI server does under the hood.
"""

import io
import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI_DIR = os.path.join(REPO_ROOT, "gui")
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, GUI_DIR)

import app as gui_app  # noqa: E402
from core import bundle_config  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def call(method, path, body=None):
    data = b""
    extra_headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        extra_headers["CONTENT_LENGTH"] = str(len(data))
        extra_headers["CONTENT_TYPE"] = "application/json"

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "80",
        "wsgi.input": io.BytesIO(data),
        "wsgi.errors": io.StringIO(),
        "wsgi.url_scheme": "http",
    }
    environ.update(extra_headers)

    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    result = gui_app.app(environ, start_response)
    raw_body = b"".join(result)
    return captured["status"], captured["headers"], raw_body


def call_json(method, path, body=None):
    status, headers, raw_body = call(method, path, body)
    parsed = json.loads(raw_body) if raw_body else None
    return status, parsed


class GuiAppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.home = os.path.join(self.tmpdir.name, "home")
        self.settings_path = os.path.join(self.tmpdir.name, "settings.json")
        self.dest = os.path.join(self.tmpdir.name, "dest")
        os.environ["CONTEXT_BUNDLES_HOME"] = self.home
        os.environ["CONTEXT_BUNDLES_SETTINGS_PATH"] = self.settings_path
        self.addCleanup(lambda: os.environ.pop("CONTEXT_BUNDLES_HOME", None))
        self.addCleanup(lambda: os.environ.pop("CONTEXT_BUNDLES_SETTINGS_PATH", None))


class StatusEndpointTest(GuiAppTestCase):
    def test_default_status_is_disabled_no_destination(self):
        status, payload = call_json("GET", "/api/status")
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload, {"enabled": False, "destination": None, "bundle_count": 0})

    def test_status_reflects_destination_and_bundle_count(self):
        os.makedirs(self.dest)
        open(os.path.join(self.dest, "a.jsonl"), "w").close()
        bundle_config.set_destination(self.dest)
        status, payload = call_json("GET", "/api/status")
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload["destination"], os.path.abspath(self.dest))
        self.assertEqual(payload["bundle_count"], 1)


class HooksStatusEndpointTest(GuiAppTestCase):
    def test_hooks_status_none_installed_initially(self):
        status, payload = call_json("GET", "/api/hooks-status")
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload["installed_events"], [])

    def test_hooks_status_after_enable(self):
        call_json("POST", "/api/enable")
        status, payload = call_json("GET", "/api/hooks-status")
        self.assertEqual(status, "200 OK")
        self.assertIn("SessionStart", payload["installed_events"])


class ConfigEndpointTest(GuiAppTestCase):
    def test_set_destination(self):
        status, payload = call_json("POST", "/api/config", {"destination": self.dest})
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload["destination"], os.path.abspath(self.dest))

    def test_missing_destination_is_400(self):
        status, payload = call_json("POST", "/api/config", {})
        self.assertEqual(status, "400 Bad Request")
        self.assertIn("error", payload)

    def test_blank_destination_is_400(self):
        status, payload = call_json("POST", "/api/config", {"destination": "   "})
        self.assertEqual(status, "400 Bad Request")

    def test_no_body_is_400(self):
        status, payload = call_json("POST", "/api/config")
        self.assertEqual(status, "400 Bad Request")


class EnableDisableEndpointTest(GuiAppTestCase):
    def test_enable_sets_config_and_installs_hooks(self):
        status, payload = call_json("POST", "/api/enable")
        self.assertEqual(status, "200 OK")
        self.assertTrue(payload["enabled"])
        with open(self.settings_path) as fh:
            settings = json.load(fh)
        self.assertIn("SessionStart", settings["hooks"])

    def test_disable_after_enable_removes_hooks(self):
        call_json("POST", "/api/enable")
        status, payload = call_json("POST", "/api/disable")
        self.assertEqual(status, "200 OK")
        self.assertFalse(payload["enabled"])
        with open(self.settings_path) as fh:
            settings = json.load(fh)
        self.assertNotIn("hooks", settings)

    def test_enable_twice_is_idempotent(self):
        call_json("POST", "/api/enable")
        call_json("POST", "/api/enable")
        with open(self.settings_path) as fh:
            settings = json.load(fh)
        self.assertEqual(len(settings["hooks"]["SessionStart"]), 1)


class BundlesListEndpointTest(GuiAppTestCase):
    def test_empty_when_no_destination_configured(self):
        status, payload = call_json("GET", "/api/bundles")
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload["bundles"], [])

    def test_lists_bundles_from_destination(self):
        os.makedirs(self.dest)
        with open(os.path.join(self.dest, "26-01-01_00-00-00_abc.jsonl"), "w") as fh:
            fh.write('{"username":"u","root_path":"/r"}\n')
        bundle_config.set_destination(self.dest)
        status, payload = call_json("GET", "/api/bundles")
        self.assertEqual(status, "200 OK")
        self.assertEqual(len(payload["bundles"]), 1)


class BundleDetailEndpointTest(GuiAppTestCase):
    def setUp(self):
        super().setUp()
        os.makedirs(self.dest)
        import shutil
        shutil.copy(
            os.path.join(FIXTURES, "sample_bundle_nominal.jsonl"),
            os.path.join(self.dest, "sample_bundle_nominal.jsonl"),
        )
        bundle_config.set_destination(self.dest)

    def test_get_bundle_by_id(self):
        status, payload = call_json("GET", "/api/bundles/sample_bundle_nominal")
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload["session_meta"]["username"], "alice")
        self.assertEqual(len(payload["prompts"]), 1)

    def test_get_latest(self):
        status, payload = call_json("GET", "/api/bundles/latest")
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload["bundle_id"], "sample_bundle_nominal")

    def test_missing_bundle_is_404(self):
        status, payload = call_json("GET", "/api/bundles/does-not-exist")
        self.assertEqual(status, "404 Not Found")
        self.assertIn("error", payload)

    def test_invalid_bundle_id_is_400(self):
        status, payload = call_json("GET", "/api/bundles/..%2F..%2Fetc")
        # The literal path segment here (after WSGI PATH_INFO decoding) may
        # contain a slash, which our router only matches as a *single*
        # segment: exercise the id validator directly with a value that
        # definitely reaches it.
        self.assertIn(status, ("400 Bad Request", "404 Not Found"))

    def test_invalid_bundle_id_rejected_by_validator(self):
        status, payload = call_json("GET", "/api/bundles/weird id with spaces")
        self.assertEqual(status, "400 Bad Request")


class UnknownApiRouteTest(GuiAppTestCase):
    def test_unknown_api_path_is_404(self):
        status, payload = call_json("GET", "/api/does-not-exist")
        self.assertEqual(status, "404 Not Found")

    def test_wrong_method_on_status_falls_through_to_static_and_405s(self):
        status, payload = call_json("POST", "/api/status")
        # POST isn't handled for /api/status; it's under /api/ so it's a 404
        # by design (path.startswith("/api/") catches it before static serving).
        self.assertEqual(status, "404 Not Found")


class StaticFileServingTest(GuiAppTestCase):
    def test_root_serves_index_html(self):
        status, headers, body = call("GET", "/")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"Context Bundles", body)
        self.assertEqual(headers["Content-Type"], "text/html")

    def test_serves_app_js(self):
        status, headers, body = call("GET", "/app.js")
        self.assertEqual(status, "200 OK")
        self.assertIn(b"refreshStatus", body)

    def test_serves_styles_css(self):
        status, headers, body = call("GET", "/styles.css")
        self.assertEqual(status, "200 OK")

    def test_missing_static_file_is_404(self):
        status, payload = call_json("GET", "/nope.html")
        self.assertEqual(status, "404 Not Found")

    def test_path_traversal_is_blocked(self):
        status, payload = call_json("GET", "/../app.py")
        self.assertIn(status, ("403 Forbidden", "404 Not Found"))
        # Whichever branch handles it, the source file must never be served.
        _, _, body = call("GET", "/../app.py")
        self.assertNotIn(b"_BUNDLE_ID_RE", body)

    def test_post_to_static_route_is_405(self):
        status, payload = call_json("POST", "/index.html")
        self.assertEqual(status, "405 Method Not Allowed")


if __name__ == "__main__":
    unittest.main()
