# AGENTS.md — context_bundles

## Purpose

Records AI coding sessions as replayable JSONL "bundles" (prompts + the
files/URLs/searches used to build context) and reloads a past bundle's
context on demand. See `README.md` for the full design rationale and
`skills/context-bundle/SKILL.md` for the user-facing command surface.

## Build & test

- No build step — Python 3 stdlib only, no dependencies to install.
- Test: `python3 -m unittest discover -s tests -v`
- Run a script directly, e.g.: `python3 core/bundle_config.py status`
- Coverage matrix: `tests/TEST_PLAN.md`

## Where things live

- `core/` — agent-agnostic logic: bundle format constants
  (`bundle_format.py`), the JSONL writer (`bundle_writer.py`), global
  config (`bundle_config.py`), listing (`bundle_list.py`), the
  dedup/filter/replay-plan builder (`bundle_load.py`), and the
  session_id → active-bundle-path pointer (`session_state.py` /
  `paths.py`). **No agent-specific code belongs here.** If you're tempted
  to import anything Claude/Cursor/Codex-specific into `core/`, it belongs
  in an adapter instead.
- `adapters/claude-code/` — the only currently-implemented integration:
  hook scripts Claude Code invokes via stdin/stdout JSON
  (`hook_session_start.py`, `hook_user_prompt_submit.py`,
  `hook_post_tool_use.py`, `hook_session_end.py`), the tool→operation
  mapping (`tool_operation_map.py`), and `install.py` (idempotent
  add/remove of exactly this adapter's entries in a `settings.json`).
- `adapters/cursor/`, `adapters/codex/` — **not implemented**, just a
  `README.md` describing the adapter contract each would need to satisfy.
  Don't assume these work.
- `skills/context-bundle/SKILL.md` — the single skill an agent invokes;
  parses one option (`status`/`enable`/`disable`/`set-destination`/`list`/
  `load`) and either shells out to a `core/`/`adapters/claude-code/` script
  or, for `load`, walks the emitted replay plan with real tool calls.
- `gui/` — local web GUI: `app.py` is a stdlib WSGI JSON API (no
  Flask/Django) wrapping `core/` + `adapters/claude-code/install.py`,
  `server.py` is the `wsgiref` entrypoint, `static/` is a vanilla
  HTML/CSS/JS frontend with no build step. It's a thin HTTP layer, not a
  new source of truth — don't put logic here that belongs in `core/`.
- `tests/` — unit tests per `core/`/adapter/gui module, integration tests
  that run the hook scripts as real subprocesses with sample stdin, GUI
  tests that call the WSGI app directly (no real socket), and
  `fixtures/*.jsonl` sample bundles for load/replay tests.

## Invariants — treat carefully

- **`core/` stays agent-agnostic.** It must run and be testable with zero
  knowledge of which coding agent (if any) is calling it. Agent-specific
  translation always lives in `adapters/<agent>/`.
- **A bundle never stores tool output/content** — only the parameters
  needed to redo an action (`path`, `url`, `query`, `command`). Don't add
  a field that captures file contents or command output; it breaks the
  "replay re-fetches live data" design and could leak sensitive data into
  a bundle at rest.
- **Every hook script fails open.** A bug, missing config, or unwritable
  destination must never block or slow the user's real session — hook
  scripts catch broadly and always exit 0. If you add a new hook, keep
  this contract.
- **`install.py enable`/`disable` only ever touch entries tagged with the
  `context_bundles/adapters/claude-code` marker** in their `command`
  string. Never make it clobber or reorder other hooks that happen to
  share the same event name.
- **Recording is off by default** (`enabled: false` in
  `~/.context_bundles/config.json`). Nothing in this repo should flip that
  on as a side effect of anything other than the skill's explicit
  `enable` option.
- **The one interactive step is `SessionStart` asking for a destination
  the first time** (hooks can't prompt the user directly — see README).
  Every other recording path must stay fully static/non-agentic.
- **The GUI binds to `127.0.0.1` by default and has no authentication.**
  It's a localhost dev dashboard, same trust model as any other. Don't add
  a `--host 0.0.0.0` default or any code path that assumes the GUI is
  network-exposed.
- **`gui/app.py` has zero new dependencies** — stdlib `wsgiref`/`json`
  only, and the frontend has zero npm dependencies/build step. Keep it
  that way; if a feature seems to need a framework, that's a signal to
  scope it down, not to add a dependency.

## When you add a new agent adapter

1. Read `adapters/cursor/README.md` first — it documents the contract
   every adapter must satisfy against `core/`.
2. Add `adapters/<agent>/` with thin translation scripts calling
   `core.bundle_config`, `core.bundle_writer`, `core.session_state`, and a
   `tool_operation_map.py` mapping that agent's action types onto
   `core.bundle_format.OPERATIONS` (unrecognized → `"other"`, never
   silently dropped).
3. Add an idempotent `install.py` following the marker-tag pattern in
   `adapters/claude-code/install.py`.
4. Add integration tests mirroring `tests/test_hooks_integration.py` and
   `tests/test_install_hooks.py` for the new adapter.
5. `core/` should need zero changes — if it does, that's a sign
   agent-specific logic leaked into it.

## Before you commit

- Run the full suite: `python3 -m unittest discover -s tests -v`.
- If you changed the bundle line schema (`core/bundle_format.py` or what
  `bundle_writer`/hooks write), update `README.md`'s format section and
  bump `SCHEMA_VERSION`.
- Never commit real bundle files, a real `~/.context_bundles/config.json`,
  or a real `~/.claude/settings.json` — only the `tests/fixtures/*.jsonl`
  samples, which use fake usernames/paths.
