"""Maps a Claude Code tool_name/tool_input pair to a context-bundle
(operation, details) pair. Kept as its own module (not inlined in the hook
script) so it can be unit tested directly without going through stdin/argv.

Only parameters needed to *redo* the operation are captured -- never tool
output/content (see bundle_format.py docstring for why).
"""

from core.bundle_writer import relativize


def _path_details(tool_input, root_path, key="file_path"):
    path = tool_input.get(key)
    if path is None:
        return {}
    if root_path:
        rel, outside = relativize(path, root_path)
        details = {"path": rel}
        if outside:
            details["outside_root"] = True
        return details
    return {"path": path}


def map_tool(tool_name, tool_input, root_path):
    """Return (operation, details) for one PostToolUse event."""
    tool_input = tool_input or {}

    if tool_name == "Read":
        return "read", _path_details(tool_input, root_path)
    if tool_name == "Write":
        return "write", _path_details(tool_input, root_path)
    if tool_name == "Edit":
        return "edit", _path_details(tool_input, root_path)
    if tool_name == "NotebookEdit":
        return "notebook_edit", _path_details(tool_input, root_path, key="notebook_path")
    if tool_name == "Bash":
        details = {}
        if "command" in tool_input:
            details["command"] = tool_input["command"]
        return "bash", details
    if tool_name == "Grep":
        details = {}
        if "pattern" in tool_input:
            details["pattern"] = tool_input["pattern"]
        if "path" in tool_input:
            details.update(_path_details(tool_input, root_path, key="path"))
        return "grep", details
    if tool_name == "Glob":
        details = {}
        if "pattern" in tool_input:
            details["pattern"] = tool_input["pattern"]
        if "path" in tool_input:
            details.update(_path_details(tool_input, root_path, key="path"))
        return "glob", details
    if tool_name == "WebSearch":
        details = {}
        if "query" in tool_input:
            details["query"] = tool_input["query"]
        return "web_search", details
    if tool_name == "WebFetch":
        details = {}
        if "url" in tool_input:
            details["url"] = tool_input["url"]
        return "web_fetch", details
    if tool_name == "AskUserQuestion":
        questions = tool_input.get("questions") or []
        texts = [q.get("question") for q in questions if isinstance(q, dict) and q.get("question")]
        return "ask_user", {"questions": texts}
    if tool_name == "Agent":
        details = {}
        for key in ("description", "subagent_type"):
            if key in tool_input:
                details[key] = tool_input[key]
        return "task_agent", details
    if tool_name == "Skill":
        details = {}
        for key in ("skill", "args"):
            if key in tool_input:
                details[key] = tool_input[key]
        return "skill_invoke", details
    if tool_name.startswith("mcp__"):
        return "mcp_tool", {"tool": tool_name}

    return "other", {"tool": tool_name}
