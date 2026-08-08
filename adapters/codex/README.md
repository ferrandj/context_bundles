# Codex CLI adapter — not implemented

Placeholder, not wired up — see `adapters/cursor/README.md` for the full
adapter contract (identical for any agent: translate that agent's own
session/prompt/tool-call events into calls against `core/`, nothing else).

Codex CLI's current hook/notify extensibility schema wasn't verified against
its docs as part of building this project, so no adapter code was written
against a guessed schema. When someone verifies the current mechanism,
building this adapter is a small isolated task: a handful of thin scripts
calling `core.bundle_config`, `core.bundle_writer`, and `core.session_state`,
plus a `tool_operation_map.py` mapping Codex's action types onto
`core.bundle_format.OPERATIONS` (with `"other"` as the catch-all for
anything unrecognized).
