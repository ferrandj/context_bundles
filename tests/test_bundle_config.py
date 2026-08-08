import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)


class BundleConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        os.environ["CONTEXT_BUNDLES_HOME"] = self.tmpdir.name
        self.addCleanup(lambda: os.environ.pop("CONTEXT_BUNDLES_HOME", None))
        from core import bundle_config
        self.bundle_config = bundle_config

    def test_load_config_defaults_when_missing(self):
        config = self.bundle_config.load_config()
        self.assertEqual(config, {"destination": None, "enabled": False})

    def test_set_destination_persists_and_expands(self):
        self.bundle_config.set_destination("~/bundles")
        config = self.bundle_config.load_config()
        self.assertEqual(config["destination"], os.path.expanduser("~/bundles"))

    def test_set_enabled_toggles(self):
        self.bundle_config.set_enabled(True)
        self.assertTrue(self.bundle_config.load_config()["enabled"])
        self.bundle_config.set_enabled(False)
        self.assertFalse(self.bundle_config.load_config()["enabled"])

    def test_load_config_survives_corrupt_file(self):
        os.makedirs(self.tmpdir.name, exist_ok=True)
        with open(self.bundle_config.config_path(), "w") as fh:
            fh.write("{not valid json")
        config = self.bundle_config.load_config()
        self.assertEqual(config, {"destination": None, "enabled": False})

    def test_status_counts_jsonl_files(self):
        dest = os.path.join(self.tmpdir.name, "dest")
        os.makedirs(dest)
        open(os.path.join(dest, "a.jsonl"), "w").close()
        open(os.path.join(dest, "b.jsonl"), "w").close()
        open(os.path.join(dest, "notes.txt"), "w").close()
        self.bundle_config.set_destination(dest)
        self.assertEqual(self.bundle_config._count_bundles(dest), 2)

    def test_main_set_destination_and_status_roundtrip(self):
        import io
        from contextlib import redirect_stdout

        dest = os.path.join(self.tmpdir.name, "dest2")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.bundle_config.main(["set-destination", dest])
        self.assertEqual(rc, 0)

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.bundle_config.main(["status"])
        self.assertEqual(rc, 0)
        self.assertIn(os.path.abspath(dest), buf.getvalue())

    def test_main_unknown_command_returns_error_code(self):
        rc = self.bundle_config.main(["bogus"])
        self.assertEqual(rc, 2)

    def test_main_no_args_returns_error_code(self):
        rc = self.bundle_config.main([])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
