import os
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from core import bundle_load


class LargeBundlePerformanceTest(unittest.TestCase):
    def test_parses_five_thousand_lines_quickly(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = os.path.join(tmp, "big.jsonl")
            with open(bundle_path, "w") as fh:
                fh.write('{"username":"u","root_path":"%s"}\n' % tmp)
                for i in range(5000):
                    fh.write(
                        '{"ts":"t","operation":"read","details":{"path":"f%d.py"}}\n' % i
                    )
            start = time.monotonic()
            plan = bundle_load.build_replay_plan(bundle_path, "big")
            elapsed = time.monotonic() - start

            self.assertEqual(len(plan["context_operations"]), 5000)
            self.assertLess(elapsed, 5.0, "parsing 5k lines took too long: %.2fs" % elapsed)


if __name__ == "__main__":
    unittest.main()
