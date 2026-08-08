"""End-to-end tests for the Claude Code adapter hook scripts: each is
invoked exactly as Claude Code would invoke it (JSON on stdin, subprocess),
with CONTEXT_BUNDLES_HOME pointed at a scratch directory so nothing touches
the real ~/.context_bundles on the test machine.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADAPTER_DIR = os.path.join(REPO_ROOT, "adapters", "claude-code")
sys.path.insert(0, REPO_ROOT)

from core import bundle_config, session_state


def run_hook(script_name, payload, home):
    env = dict(os.environ)
    env["CONTEXT_BUNDLES_HOME"] = home
    result = subprocess.run(
        [sys.executable, os.path.join(ADAPTER_DIR, script_name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    return result


class HookSessionStartTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.home = os.path.join(self.tmpdir.name, "home")
        self.dest = os.path.join(self.tmpdir.name, "dest")
        os.environ["CONTEXT_BUNDLES_HOME"] = self.home

    def tearDown(self):
        os.environ.pop("CONTEXT_BUNDLES_HOME", None)

    def test_disabled_creates_nothing(self):
        bundle_config.set_enabled(False)
        result = run_hook(
            "hook_session_start.py",
            {"session_id": "s1", "cwd": "/some/project"},
            self.home,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIsNone(session_state.get_active_bundle("s1"))

    def test_enabled_no_destination_emits_ask_message_and_creates_no_bundle(self):
        bundle_config.set_enabled(True)
        result = run_hook(
            "hook_session_start.py",
            {"session_id": "s2", "cwd": "/some/project"},
            self.home,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("destination", result.stdout.lower())
        self.assertIsNone(session_state.get_active_bundle("s2"))

    def test_enabled_with_destination_creates_bundle_and_pointer(self):
        bundle_config.set_enabled(True)
        bundle_config.set_destination(self.dest)
        result = run_hook(
            "hook_session_start.py",
            {"session_id": "s3", "cwd": "/some/project"},
            self.home,
        )
        self.assertEqual(result.returncode, 0)
        bundle_path = session_state.get_active_bundle("s3")
        self.assertIsNotNone(bundle_path)
        self.assertTrue(os.path.exists(bundle_path))
        with open(bundle_path) as fh:
            meta = json.loads(fh.readline())
        self.assertEqual(meta["root_path"], "/some/project")
        self.assertEqual(meta["session_id"], "s3")

    def test_second_session_start_for_same_id_does_not_duplicate_meta_line(self):
        bundle_config.set_enabled(True)
        bundle_config.set_destination(self.dest)
        payload = {"session_id": "s4", "cwd": "/proj"}
        run_hook("hook_session_start.py", payload, self.home)
        bundle_path_1 = session_state.get_active_bundle("s4")
        run_hook("hook_session_start.py", payload, self.home)
        bundle_path_2 = session_state.get_active_bundle("s4")
        # A fresh SessionStart always allocates a new filename (new session
        # id firing twice is unusual, but should still never corrupt a file
        # -- each new bundle_path gets exactly one meta line).
        for p in {bundle_path_1, bundle_path_2}:
            with open(p) as fh:
                lines = fh.readlines()
            self.assertEqual(len(lines), 1)


class HookUserPromptSubmitTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.home = os.path.join(self.tmpdir.name, "home")
        self.dest = os.path.join(self.tmpdir.name, "dest")
        os.environ["CONTEXT_BUNDLES_HOME"] = self.home
        bundle_config.set_enabled(True)
        bundle_config.set_destination(self.dest)

    def tearDown(self):
        os.environ.pop("CONTEXT_BUNDLES_HOME", None)

    def test_appends_prompt_to_active_bundle(self):
        run_hook("hook_session_start.py", {"session_id": "p1", "cwd": "/proj"}, self.home)
        run_hook(
            "hook_user_prompt_submit.py",
            {"session_id": "p1", "user_prompt": "hello world"},
            self.home,
        )
        bundle_path = session_state.get_active_bundle("p1")
        with open(bundle_path) as fh:
            lines = fh.readlines()
        self.assertEqual(len(lines), 2)
        entry = json.loads(lines[1])
        self.assertEqual(entry["operation"], "prompt")
        self.assertEqual(entry["details"]["text"], "hello world")

    def test_no_active_bundle_is_a_silent_noop(self):
        result = run_hook(
            "hook_user_prompt_submit.py",
            {"session_id": "never-started", "user_prompt": "hi"},
            self.home,
        )
        self.assertEqual(result.returncode, 0)

    def test_disabled_does_not_append(self):
        run_hook("hook_session_start.py", {"session_id": "p2", "cwd": "/proj"}, self.home)
        bundle_path = session_state.get_active_bundle("p2")
        bundle_config.set_enabled(False)
        run_hook(
            "hook_user_prompt_submit.py",
            {"session_id": "p2", "user_prompt": "hi"},
            self.home,
        )
        with open(bundle_path) as fh:
            lines = fh.readlines()
        self.assertEqual(len(lines), 1)


class HookPostToolUseTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.home = os.path.join(self.tmpdir.name, "home")
        self.dest = os.path.join(self.tmpdir.name, "dest")
        self.project = os.path.join(self.tmpdir.name, "proj")
        os.makedirs(self.project)
        os.environ["CONTEXT_BUNDLES_HOME"] = self.home
        bundle_config.set_enabled(True)
        bundle_config.set_destination(self.dest)
        run_hook("hook_session_start.py", {"session_id": "t1", "cwd": self.project}, self.home)
        self.bundle_path = session_state.get_active_bundle("t1")

    def tearDown(self):
        os.environ.pop("CONTEXT_BUNDLES_HOME", None)

    def _last_entry(self):
        with open(self.bundle_path) as fh:
            lines = fh.readlines()
        return json.loads(lines[-1])

    def test_read_tool_appends_relative_path(self):
        run_hook(
            "hook_post_tool_use.py",
            {
                "session_id": "t1",
                "tool_name": "Read",
                "tool_input": {"file_path": os.path.join(self.project, "src/a.py")},
            },
            self.home,
        )
        entry = self._last_entry()
        self.assertEqual(entry["operation"], "read")
        self.assertEqual(entry["details"]["path"], "src/a.py")

    def test_unknown_tool_falls_back_to_other(self):
        run_hook(
            "hook_post_tool_use.py",
            {"session_id": "t1", "tool_name": "BrandNewTool", "tool_input": {}},
            self.home,
        )
        entry = self._last_entry()
        self.assertEqual(entry["operation"], "other")
        self.assertEqual(entry["details"]["tool"], "BrandNewTool")

    def test_missing_tool_name_is_noop(self):
        before = os.path.getsize(self.bundle_path)
        run_hook("hook_post_tool_use.py", {"session_id": "t1", "tool_input": {}}, self.home)
        after = os.path.getsize(self.bundle_path)
        self.assertEqual(before, after)


class HookSessionEndTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.home = os.path.join(self.tmpdir.name, "home")
        self.dest = os.path.join(self.tmpdir.name, "dest")
        os.environ["CONTEXT_BUNDLES_HOME"] = self.home
        bundle_config.set_enabled(True)
        bundle_config.set_destination(self.dest)

    def tearDown(self):
        os.environ.pop("CONTEXT_BUNDLES_HOME", None)

    def test_clears_pointer_but_keeps_bundle_file(self):
        run_hook("hook_session_start.py", {"session_id": "e1", "cwd": "/proj"}, self.home)
        bundle_path = session_state.get_active_bundle("e1")
        run_hook("hook_session_end.py", {"session_id": "e1"}, self.home)
        self.assertIsNone(session_state.get_active_bundle("e1"))
        self.assertTrue(os.path.exists(bundle_path))


if __name__ == "__main__":
    unittest.main()
