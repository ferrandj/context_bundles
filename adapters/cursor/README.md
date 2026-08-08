# Cursor adapter — not implemented

This folder is a placeholder. It is **not wired up** to anything and Cursor
will not record bundles until someone builds this adapter.

Cursor's own hook/event schema wasn't verified against current docs as part
of building this project (see `context_bundles/README.md` for why: avoiding
shipping an adapter built on a guessed schema that silently breaks). Building
it is meant to be a small, isolated task, not a rewrite of the system —
`core/` already contains everything agent-agnostic.

## The adapter contract

Any new adapter is just a small translation layer that calls into
`core/` at the right moments. Concretely, an adapter needs to:

1. **On session start**: call `core.bundle_config.load_config()`. If
   `enabled` is false, do nothing. If `enabled` is true but `destination` is
   unset, surface a message asking the host agent to collect a destination
   from the user (however that agent's tooling supports asking a question)
   and persist it with `core.bundle_config.set_destination(path)`. Otherwise
   call `core.bundle_writer.new_bundle_filename()`, then
   `core.bundle_writer.write_session_meta(bundle_path, username, root_path,
   session_id)`, then `core.session_state.set_active_bundle(session_id,
   bundle_path)`.

2. **On each user prompt**: `core.session_state.get_active_bundle(session_id)`
   then `core.bundle_writer.append_operation(bundle_path, "prompt", {"text": ...})`.

3. **On each tool/action the agent takes**: map that agent's action type to
   one of the operations in `core.bundle_format.OPERATIONS` (add a
   `tool_operation_map.py` alongside your hook scripts, following the
   pattern in `adapters/claude-code/tool_operation_map.py` — anything
   unrecognized should still map to `"other"` with the raw action name
   preserved in `details`, never silently dropped). Then call
   `core.bundle_writer.append_operation(bundle_path, operation, details)`.
   Only store the parameters needed to redo the action (path/url/query/
   command) — never the tool's output/content.

4. **On session end**: `core.session_state.clear_active_bundle(session_id)`.

5. **Install/uninstall**: however Cursor lets you register these hooks
   persistently (its own config file, plugin manifest, etc.) — follow the
   idempotent merge/remove pattern in
   `adapters/claude-code/install.py` (tag entries with a marker string so
   `disable` only removes entries this adapter added).

Every one of those `core.*` functions is already implemented and unit
tested in `context_bundles/tests/` — an adapter should need zero new logic
in `core/`, only the translation from Cursor's event shape into these calls.
