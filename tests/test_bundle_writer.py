import datetime
import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from core import bundle_writer
from core.bundle_format import FILENAME_RE


class NewBundleFilenameTest(unittest.TestCase):
    def test_matches_expected_pattern(self):
        name = bundle_writer.new_bundle_filename(
            now=datetime.datetime(2026, 8, 7, 23, 5, 9)
        )
        self.assertTrue(FILENAME_RE.match(name), name)
        self.assertTrue(name.startswith("26-08-07_23-05-09_"))

    def test_unique_across_calls(self):
        now = datetime.datetime(2026, 8, 7, 23, 5, 9)
        a = bundle_writer.new_bundle_filename(now=now)
        b = bundle_writer.new_bundle_filename(now=now)
        self.assertNotEqual(a, b)


class RelativizeTest(unittest.TestCase):
    def test_path_under_root(self):
        rel, outside = bundle_writer.relativize("/a/b/c/file.py", "/a/b")
        self.assertEqual(rel, "c/file.py")
        self.assertFalse(outside)

    def test_path_outside_root(self):
        rel, outside = bundle_writer.relativize("/x/y/file.py", "/a/b")
        self.assertTrue(outside)
        self.assertEqual(rel, "/x/y/file.py")

    def test_root_itself(self):
        rel, outside = bundle_writer.relativize("/a/b", "/a/b")
        self.assertEqual(rel, ".")
        self.assertFalse(outside)


class AppendAndMetaTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.bundle_path = os.path.join(self.tmpdir.name, "sub", "bundle.jsonl")

    def test_write_session_meta_creates_file_with_flat_keys(self):
        created = bundle_writer.write_session_meta(
            self.bundle_path, username="jeremie", root_path="/work/proj",
            session_id="abc123", started_at="2026-08-07T00:00:00+00:00",
        )
        self.assertTrue(created)
        with open(self.bundle_path) as fh:
            lines = fh.readlines()
        self.assertEqual(len(lines), 1)
        meta = json.loads(lines[0])
        self.assertEqual(meta["username"], "jeremie")
        self.assertEqual(meta["root_path"], "/work/proj")
        self.assertEqual(meta["session_id"], "abc123")
        self.assertIn("schema_version", meta)

    def test_write_session_meta_idempotent(self):
        bundle_writer.write_session_meta(
            self.bundle_path, "jeremie", "/work/proj", "abc123"
        )
        second = bundle_writer.write_session_meta(
            self.bundle_path, "someone-else", "/other", "xyz"
        )
        self.assertFalse(second)
        with open(self.bundle_path) as fh:
            lines = fh.readlines()
        self.assertEqual(len(lines), 1)
        meta = json.loads(lines[0])
        self.assertEqual(meta["username"], "jeremie")

    def test_append_operation_appends_one_json_line(self):
        bundle_writer.write_session_meta(self.bundle_path, "u", "/r", "s1")
        bundle_writer.append_operation(self.bundle_path, "read", {"path": "a.py"})
        bundle_writer.append_operation(self.bundle_path, "bash", {"command": "ls"})
        with open(self.bundle_path) as fh:
            lines = [json.loads(l) for l in fh.readlines()]
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[1]["operation"], "read")
        self.assertEqual(lines[1]["details"]["path"], "a.py")
        self.assertIn("ts", lines[1])
        self.assertEqual(lines[2]["operation"], "bash")

    def test_read_bundle_lines_flags_malformed_without_raising(self):
        os.makedirs(os.path.dirname(self.bundle_path), exist_ok=True)
        with open(self.bundle_path, "w") as fh:
            fh.write('{"a": 1}\n')
            fh.write("not json at all\n")
            fh.write('{"b": 2}\n')
        results = list(bundle_writer.read_bundle_lines(self.bundle_path))
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0][1], {"a": 1})
        self.assertIsNone(results[1][1])
        self.assertEqual(results[2][1], {"b": 2})

    def test_read_bundle_lines_skips_blank_lines(self):
        os.makedirs(os.path.dirname(self.bundle_path), exist_ok=True)
        with open(self.bundle_path, "w") as fh:
            fh.write('{"a": 1}\n\n\n{"b": 2}\n')
        results = list(bundle_writer.read_bundle_lines(self.bundle_path))
        self.assertEqual(len(results), 2)

    def test_read_session_meta_missing_file(self):
        self.assertIsNone(bundle_writer.read_session_meta("/no/such/file.jsonl"))


if __name__ == "__main__":
    unittest.main()
