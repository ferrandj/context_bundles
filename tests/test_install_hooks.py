import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADAPTER_DIR = os.path.join(REPO_ROOT, "adapters", "claude-code")
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, ADAPTER_DIR)

import install


class InstallHooksTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.settings_path = os.path.join(self.tmpdir.name, "settings.json")

    def _write_settings(self, data):
        with open(self.settings_path, "w") as fh:
            json.dump(data, fh)

    def _read_settings(self):
        with open(self.settings_path) as fh:
            return json.load(fh)

    def test_enable_on_missing_settings_file_creates_it(self):
        install.enable(self.settings_path)
        settings = self._read_settings()
        self.assertIn("SessionStart", settings["hooks"])
        self.assertIn("PostToolUse", settings["hooks"])
        self.assertIn("UserPromptSubmit", settings["hooks"])
        self.assertIn("SessionEnd", settings["hooks"])

    def test_enable_preserves_unrelated_settings_and_hooks(self):
        self._write_settings({
            "model": "sonnet",
            "hooks": {
                "SessionStart": [
                    {"matcher": "*", "hooks": [
                        {"type": "command", "command": "bash /some/other/hook.sh"}
                    ]}
                ]
            },
        })
        install.enable(self.settings_path)
        settings = self._read_settings()
        self.assertEqual(settings["model"], "sonnet")
        session_start_entries = settings["hooks"]["SessionStart"]
        self.assertEqual(len(session_start_entries), 2)
        commands = [h["command"] for e in session_start_entries for h in e["hooks"]]
        self.assertIn("bash /some/other/hook.sh", commands)
        self.assertTrue(any("context_bundles" in c for c in commands))

    def test_enable_twice_is_idempotent(self):
        install.enable(self.settings_path)
        install.enable(self.settings_path)
        settings = self._read_settings()
        session_start_entries = settings["hooks"]["SessionStart"]
        self.assertEqual(len(session_start_entries), 1)

    def test_disable_removes_only_our_entries(self):
        self._write_settings({
            "hooks": {
                "SessionStart": [
                    {"matcher": "*", "hooks": [
                        {"type": "command", "command": "bash /some/other/hook.sh"}
                    ]}
                ]
            },
        })
        install.enable(self.settings_path)
        install.disable(self.settings_path)
        settings = self._read_settings()
        session_start_entries = settings["hooks"]["SessionStart"]
        self.assertEqual(len(session_start_entries), 1)
        self.assertEqual(
            session_start_entries[0]["hooks"][0]["command"], "bash /some/other/hook.sh"
        )
        # events we added and that had nothing else in them are gone entirely
        self.assertNotIn("PostToolUse", settings["hooks"])

    def test_disable_on_never_enabled_settings_is_noop(self):
        self._write_settings({"model": "sonnet"})
        install.disable(self.settings_path)
        settings = self._read_settings()
        self.assertEqual(settings, {"model": "sonnet"})

    def test_status_reports_installed_events(self):
        install.enable(self.settings_path)
        status = install.status(self.settings_path)
        self.assertIn("SessionStart", status["installed_events"])
        self.assertIn("PostToolUse", status["installed_events"])

    def test_status_before_enable_reports_none_installed(self):
        status = install.status(self.settings_path)
        self.assertEqual(status["installed_events"], [])


if __name__ == "__main__":
    unittest.main()
