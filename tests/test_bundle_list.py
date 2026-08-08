import json
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from core import bundle_list


class BundleListTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def _write(self, name, content):
        path = os.path.join(self.tmpdir.name, name)
        with open(path, "w") as fh:
            fh.write(content)
        return path

    def test_empty_destination_returns_empty_list(self):
        self.assertEqual(bundle_list.list_bundles(self.tmpdir.name), [])

    def test_none_destination_returns_empty_list(self):
        self.assertEqual(bundle_list.list_bundles(None), [])

    def test_missing_destination_dir_returns_empty_list(self):
        self.assertEqual(bundle_list.list_bundles("/no/such/dir"), [])

    def test_lists_well_formed_bundle_with_meta(self):
        self._write(
            "26-08-07_10-00-00_11111111-1111-1111-1111-111111111111.jsonl",
            '{"username": "u", "root_path": "/r", "session_id": "s1"}\n'
            '{"ts": "t", "operation": "prompt", "details": {"text": "hi"}}\n',
        )
        entries = bundle_list.list_bundles(self.tmpdir.name)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertTrue(entry["well_formed_name"])
        self.assertEqual(entry["line_count"], 2)
        self.assertEqual(entry["session_meta"]["username"], "u")
        self.assertIsNone(entry["error"])

    def test_ignores_non_jsonl_files(self):
        self._write("readme.txt", "hello")
        self.assertEqual(bundle_list.list_bundles(self.tmpdir.name), [])

    def test_flags_malformed_meta_line_without_crashing(self):
        self._write("weird.jsonl", "not json\nmore text\n")
        entries = bundle_list.list_bundles(self.tmpdir.name)
        self.assertEqual(len(entries), 1)
        self.assertIsNotNone(entries[0]["error"])
        self.assertIsNone(entries[0]["session_meta"])

    def test_flags_empty_file(self):
        self._write("empty.jsonl", "")
        entries = bundle_list.list_bundles(self.tmpdir.name)
        self.assertEqual(entries[0]["error"], "empty file")

    def test_sorted_newest_first_by_filename(self):
        self._write("25-01-01_00-00-00_11111111-1111-1111-1111-111111111111.jsonl", "{}\n")
        self._write("26-01-01_00-00-00_22222222-2222-2222-2222-222222222222.jsonl", "{}\n")
        entries = bundle_list.list_bundles(self.tmpdir.name)
        self.assertTrue(entries[0]["filename"].startswith("26-"))
        self.assertTrue(entries[1]["filename"].startswith("25-"))


if __name__ == "__main__":
    unittest.main()
