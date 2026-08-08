import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

from core import bundle_load


class ResolveBundlePathTest(unittest.TestCase):
    def test_resolve_by_exact_id(self):
        path, resolved_id = bundle_load.resolve_bundle_path(
            "sample_bundle_nominal", FIXTURES
        )
        self.assertTrue(path.endswith("sample_bundle_nominal.jsonl"))
        self.assertEqual(resolved_id, "sample_bundle_nominal")

    def test_resolve_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            bundle_load.resolve_bundle_path("does-not-exist", FIXTURES)

    def test_resolve_no_destination_raises(self):
        with self.assertRaises(FileNotFoundError):
            bundle_load.resolve_bundle_path("anything", None)

    def test_resolve_latest_picks_newest_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in (
                "25-01-01_00-00-00_11111111-1111-1111-1111-111111111111.jsonl",
                "26-01-01_00-00-00_22222222-2222-2222-2222-222222222222.jsonl",
            ):
                with open(os.path.join(tmp, name), "w") as fh:
                    fh.write('{"username":"u","root_path":"/r"}\n')
            path, resolved_id = bundle_load.resolve_bundle_path("latest", tmp)
            self.assertIn("26-01-01", path)


class BuildReplayPlanTest(unittest.TestCase):
    def _plan(self, fixture_name):
        path = os.path.join(FIXTURES, fixture_name)
        return bundle_load.build_replay_plan(path, fixture_name[: -len(".jsonl")])

    def test_nominal_bundle_filters_to_replayable_ops(self):
        plan = self._plan("sample_bundle_nominal.jsonl")
        self.assertEqual(plan["session_meta"]["username"], "alice")
        self.assertEqual(len(plan["prompts"]), 1)
        self.assertEqual(plan["prompts"][0]["text"], "Explain the auth module")

        ops = [op["operation"] for op in plan["context_operations"]]
        self.assertEqual(ops, ["read", "grep", "web_fetch", "web_search"])
        # edit, write, bash, ask_user, other -> excluded
        self.assertEqual(plan["stats"]["excluded"], 5)
        self.assertEqual(plan["stats"]["deduped_from"], 0)
        self.assertEqual(plan["stats"]["malformed"], 0)

    def test_nominal_bundle_flags_stale_reads(self):
        plan = self._plan("sample_bundle_nominal.jsonl")
        read_op = next(op for op in plan["context_operations"] if op["operation"] == "read")
        # root_path in the fixture ("/home/alice/proj") doesn't exist on the
        # test machine, so the referenced file must be flagged stale.
        self.assertTrue(read_op["stale"])

    def test_malformed_line_is_counted_and_skipped(self):
        plan = self._plan("sample_bundle_malformed_line.jsonl")
        self.assertEqual(plan["stats"]["malformed"], 1)
        self.assertEqual(len(plan["prompts"]), 1)
        ops = [op["operation"] for op in plan["context_operations"]]
        self.assertEqual(ops, ["read"])

    def test_only_prompts_bundle_has_no_context_operations(self):
        plan = self._plan("sample_bundle_only_prompts.jsonl")
        self.assertEqual(len(plan["prompts"]), 2)
        self.assertEqual(plan["context_operations"], [])
        self.assertEqual(plan["stats"]["excluded"], 0)

    def test_duplicate_reads_are_deduplicated_preserving_order(self):
        plan = self._plan("sample_bundle_duplicates.jsonl")
        paths = [op["details"]["path"] for op in plan["context_operations"]]
        self.assertEqual(paths, ["src/main.py", "src/other.py"])
        self.assertEqual(plan["stats"]["deduped_from"], 2)

    def test_stale_flag_false_when_file_actually_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "real.txt"), "w").close()
            bundle_path = os.path.join(tmp, "b.jsonl")
            with open(bundle_path, "w") as fh:
                fh.write('{"username":"u","root_path":"%s"}\n' % tmp)
                fh.write('{"ts":"t","operation":"read","details":{"path":"real.txt"}}\n')
            plan = bundle_load.build_replay_plan(bundle_path, "b")
            self.assertFalse(plan["context_operations"][0]["stale"])


class MainCliTest(unittest.TestCase):
    def test_main_prints_error_json_for_missing_bundle(self):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = bundle_load.main(["nope", "--dir", FIXTURES])
        self.assertEqual(rc, 1)
        self.assertIn("error", buf.getvalue())

    def test_main_no_args_returns_usage_error(self):
        rc = bundle_load.main([])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
