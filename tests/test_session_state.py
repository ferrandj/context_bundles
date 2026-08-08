import datetime
import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)


class SessionStateTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        os.environ["CONTEXT_BUNDLES_HOME"] = self.tmpdir.name
        self.addCleanup(lambda: os.environ.pop("CONTEXT_BUNDLES_HOME", None))
        # core.paths reads the env var lazily via os.environ.get(), so no
        # module reload is needed between tests.
        from core import session_state
        self.session_state = session_state

    def test_set_and_get_active_bundle(self):
        self.session_state.set_active_bundle("sess-1", "/tmp/bundle1.jsonl")
        self.assertEqual(
            self.session_state.get_active_bundle("sess-1"), "/tmp/bundle1.jsonl"
        )

    def test_get_unknown_session_returns_none(self):
        self.assertIsNone(self.session_state.get_active_bundle("never-seen"))

    def test_clear_active_bundle(self):
        self.session_state.set_active_bundle("sess-2", "/tmp/bundle2.jsonl")
        self.session_state.clear_active_bundle("sess-2")
        self.assertIsNone(self.session_state.get_active_bundle("sess-2"))

    def test_clear_unknown_session_is_noop(self):
        self.session_state.clear_active_bundle("never-existed")  # must not raise

    def test_session_id_is_sanitized_for_path_traversal(self):
        malicious = "../../etc/passwd"
        self.session_state.set_active_bundle(malicious, "/tmp/x.jsonl")
        from core.paths import session_pointer_path
        p = session_pointer_path(malicious)
        self.assertTrue(p.startswith(self.tmpdir.name))
        self.assertNotIn("..", os.path.relpath(p, self.tmpdir.name))

    def test_sweep_removes_stale_pointers_keeps_fresh(self):
        from core.paths import state_dir
        os.makedirs(state_dir(), exist_ok=True)
        now = datetime.datetime.now(datetime.timezone.utc)

        fresh_path = os.path.join(state_dir(), "fresh.json")
        with open(fresh_path, "w") as fh:
            json.dump({"bundle_path": "/x", "created_at": now.isoformat()}, fh)

        stale_time = now - datetime.timedelta(hours=48)
        stale_path = os.path.join(state_dir(), "stale.json")
        with open(stale_path, "w") as fh:
            json.dump({"bundle_path": "/x", "created_at": stale_time.isoformat()}, fh)

        removed = self.session_state.sweep_stale_pointers(now=now)
        self.assertEqual(removed, 1)
        self.assertTrue(os.path.exists(fresh_path))
        self.assertFalse(os.path.exists(stale_path))

    def test_sweep_removes_corrupt_pointer_files(self):
        from core.paths import state_dir
        os.makedirs(state_dir(), exist_ok=True)
        corrupt_path = os.path.join(state_dir(), "corrupt.json")
        with open(corrupt_path, "w") as fh:
            fh.write("not valid json{{{")
        removed = self.session_state.sweep_stale_pointers()
        self.assertEqual(removed, 1)
        self.assertFalse(os.path.exists(corrupt_path))

    def test_sweep_on_missing_state_dir_returns_zero(self):
        self.assertEqual(self.session_state.sweep_stale_pointers(), 0)


if __name__ == "__main__":
    unittest.main()
