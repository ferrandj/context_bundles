"""Agent-agnostic constants describing the context-bundle JSONL format.

No code in this module talks to any specific AI coding agent. Adapters
(under ``adapters/<agent>/``) translate that agent's own event format into
calls against ``bundle_writer``, using the vocabulary defined here.
"""

import re

SCHEMA_VERSION = 1

# Filename pattern: YY-MM-DD_HH-MM-SS_<uuid4>.jsonl
FILENAME_RE = re.compile(
    r"^\d{2}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl$"
)

# The full set of operation types a bundle line may declare. "other" is the
# catch-all so an adapter never has to silently drop an event it doesn't
# recognize -- it always has a bucket to put it in.
OPERATIONS = frozenset(
    {
        "prompt",  # a user prompt / instruction was submitted
        "read",  # a file was read
        "write",  # a file was created or fully overwritten
        "edit",  # a file was partially modified
        "bash",  # a shell command was executed
        "grep",  # a text/regex search over files
        "glob",  # a filename-pattern listing
        "web_search",  # a web search query
        "web_fetch",  # a URL was fetched
        "ask_user",  # the agent asked the user a multiple-choice/clarifying question
        "task_agent",  # a sub-agent/task was spawned
        "notebook_edit",  # a notebook cell was edited
        "skill_invoke",  # a packaged skill was invoked
        "mcp_tool",  # a generic MCP server tool call
        "other",  # anything not covered above; details.tool holds the raw name
    }
)

# Operations that are safe and meaningful to replay when reconstructing
# context: they only *read* external state (files, the web, the user's
# original prompts) and are idempotent/side-effect-free to redo.
REPLAYABLE_OPERATIONS = frozenset(
    {"prompt", "read", "web_fetch", "web_search", "grep", "glob"}
)
