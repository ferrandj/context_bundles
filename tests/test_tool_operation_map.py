import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADAPTER_DIR = os.path.join(REPO_ROOT, "adapters", "claude-code")
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, ADAPTER_DIR)

from tool_operation_map import map_tool


class MapToolTest(unittest.TestCase):
    def test_read(self):
        op, details = map_tool("Read", {"file_path": "/root/src/a.py"}, "/root")
        self.assertEqual(op, "read")
        self.assertEqual(details, {"path": "src/a.py"})

    def test_read_outside_root(self):
        op, details = map_tool("Read", {"file_path": "/elsewhere/a.py"}, "/root")
        self.assertEqual(op, "read")
        self.assertTrue(details["outside_root"])
        self.assertEqual(details["path"], "/elsewhere/a.py")

    def test_write(self):
        op, details = map_tool("Write", {"file_path": "/root/new.py"}, "/root")
        self.assertEqual(op, "write")
        self.assertEqual(details["path"], "new.py")

    def test_edit(self):
        op, _ = map_tool("Edit", {"file_path": "/root/a.py"}, "/root")
        self.assertEqual(op, "edit")

    def test_notebook_edit_uses_notebook_path_key(self):
        op, details = map_tool("NotebookEdit", {"notebook_path": "/root/nb.ipynb"}, "/root")
        self.assertEqual(op, "notebook_edit")
        self.assertEqual(details["path"], "nb.ipynb")

    def test_bash(self):
        op, details = map_tool("Bash", {"command": "ls -la"}, "/root")
        self.assertEqual(op, "bash")
        self.assertEqual(details["command"], "ls -la")

    def test_grep(self):
        op, details = map_tool("Grep", {"pattern": "foo", "path": "/root/src"}, "/root")
        self.assertEqual(op, "grep")
        self.assertEqual(details["pattern"], "foo")
        self.assertEqual(details["path"], "src")

    def test_glob(self):
        op, details = map_tool("Glob", {"pattern": "**/*.py"}, "/root")
        self.assertEqual(op, "glob")
        self.assertEqual(details["pattern"], "**/*.py")
        self.assertNotIn("path", details)

    def test_web_search(self):
        op, details = map_tool("WebSearch", {"query": "python jsonl"}, "/root")
        self.assertEqual(op, "web_search")
        self.assertEqual(details["query"], "python jsonl")

    def test_web_fetch(self):
        op, details = map_tool("WebFetch", {"url": "https://example.com"}, "/root")
        self.assertEqual(op, "web_fetch")
        self.assertEqual(details["url"], "https://example.com")

    def test_ask_user(self):
        op, details = map_tool(
            "AskUserQuestion",
            {"questions": [{"question": "A or B?"}, {"question": "Sure?"}]},
            "/root",
        )
        self.assertEqual(op, "ask_user")
        self.assertEqual(details["questions"], ["A or B?", "Sure?"])

    def test_agent(self):
        op, details = map_tool(
            "Agent", {"description": "explore repo", "subagent_type": "Explore"}, "/root"
        )
        self.assertEqual(op, "task_agent")
        self.assertEqual(details["subagent_type"], "Explore")

    def test_skill(self):
        op, details = map_tool("Skill", {"skill": "context-bundle", "args": "status"}, "/root")
        self.assertEqual(op, "skill_invoke")
        self.assertEqual(details["skill"], "context-bundle")

    def test_mcp_tool(self):
        op, details = map_tool("mcp__slack__send", {"channel": "#eng"}, "/root")
        self.assertEqual(op, "mcp_tool")
        self.assertEqual(details, {"tool": "mcp__slack__send"})

    def test_unknown_tool_falls_back_to_other(self):
        op, details = map_tool("SomeBrandNewTool", {"x": 1}, "/root")
        self.assertEqual(op, "other")
        self.assertEqual(details, {"tool": "SomeBrandNewTool"})

    def test_no_root_path_still_returns_raw_path(self):
        op, details = map_tool("Read", {"file_path": "/a/b.py"}, None)
        self.assertEqual(op, "read")
        self.assertEqual(details, {"path": "/a/b.py"})

    def test_missing_expected_key_returns_empty_details(self):
        op, details = map_tool("Read", {}, "/root")
        self.assertEqual(op, "read")
        self.assertEqual(details, {})


if __name__ == "__main__":
    unittest.main()
