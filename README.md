# context_bundles

Record what an AI coding session actually did — prompts, files it read,
URLs it fetched, searches it ran — as a small JSONL file, and later reload
a past session's context (in the same tool, or in principle any other) by
replaying just the parts that reconstruct context.

## Why

Two goals drove the design:

- **The bundle format is agent-agnostic.** A `.jsonl` bundle is a plain,
  documented format (see below) with no Claude-specific fields. Any tool
  that can write/read JSON lines can produce or consume one.
- **Everything that can be static, is.** Recording, deduplication,
  filtering, config, and hook installation are deterministic Python 3
  stdlib scripts with no LLM involved — see "Where an agent is actually
  required" below for the two narrow exceptions, and why they can't be
  avoided.

## Layout

```
core/                 agent-agnostic: format spec, writer, config, list, replay-plan builder
adapters/claude-code/  fully implemented + tested integration for Claude Code (hooks)
adapters/cursor/       adapter contract documented, not implemented
adapters/codex/        adapter contract documented, not implemented
skills/context-bundle/ the one skill: status/enable/disable/set-destination/list/load
gui/                   local web GUI (stdlib WSGI backend + vanilla JS frontend)
tests/                 unit + integration tests (python3 -m unittest discover -s tests)
```

## Bundle format

One `.jsonl` file per AI session, named
`YY-MM-DD_HH-MM-SS_<uuid4>.jsonl` (timestamp of session start).

Line 1 is always the session's metadata:
```json
{"username": "jeremie", "root_path": "/Users/jeremie/WORK/some-project", "session_id": "...", "started_at": "2026-08-08T12:00:00+00:00", "schema_version": 1}
```

Every following line is one recorded action:
```json
{"ts": "2026-08-08T12:00:03+00:00", "operation": "read", "details": {"path": "src/main.py"}}
```

`operation` is one of: `prompt`, `read`, `write`, `edit`, `bash`, `grep`,
`glob`, `web_search`, `web_fetch`, `ask_user`, `task_agent`,
`notebook_edit`, `skill_invoke`, `mcp_tool`, `other` (catch-all, with the
raw tool name preserved in `details.tool` so nothing is silently dropped).
See `core/bundle_format.py` for the authoritative list.

`details.path` is relative to `root_path` when the target is under it;
otherwise it's absolute and `details.outside_root: true` is set. Bundles
never store file/URL *content* — only what's needed to redo the action —
so reloading a bundle re-fetches live data rather than replaying a stale
cache.

## Where an agent is actually required

Two steps genuinely can't be done by a plain script, and only these two:

1. **First-time destination prompt.** Hooks can't ask an interactive
   question. A static `SessionStart` hook detects "enabled, no destination
   set" and asks the agent (via a `systemMessage`) to collect an answer
   from the user and persist it with `core/bundle_config.py
   set-destination`. Every session after that is pure static hook
   execution.
2. **Replaying reads to rebuild context.** Only an agent can populate its
   own context window. `core/bundle_load.py` does all the static work
   (parse, dedupe, filter to `prompt`/`read`/`web_fetch`/`web_search`/
   `grep`/`glob`, flag stale paths) and emits a replay plan; the
   `context-bundle` skill then walks that plan issuing real tool calls.

## Usage (Claude Code)

The skill lives at `skills/context-bundle/SKILL.md`. Copy (or symlink) the
whole `context-bundle` folder into `~/.claude/skills/` (global) or a
project's `.claude/skills/` to make `/context-bundle` available, then:

```
/context-bundle status
/context-bundle enable            # asks where to store bundles the first time
/context-bundle list
/context-bundle load latest
/context-bundle disable
```

`enable`/`disable` add/remove exactly four hook entries (`SessionStart`,
`UserPromptSubmit`, `PostToolUse`, `SessionEnd`) in `~/.claude/settings.json`,
leaving every other hook untouched. This repo does not modify your real
`~/.claude/settings.json` on its own — recording stays off until you
explicitly run `enable`.

## GUI

A local dashboard for the same operations the skill exposes: enable/
disable recording, edit the destination, browse recorded bundles, and
inspect a bundle's replay plan (prompts + which reads/searches/fetches
would be redone, with stale paths flagged).

```
python3 gui/server.py            # opens http://127.0.0.1:8765/ in your browser
python3 gui/server.py --no-open --port 9000
```

Built with the Python 3 standard library only (`wsgiref` + a vanilla
HTML/CSS/JS frontend, no npm/build step) — same zero-dependency,
easy-to-test philosophy as the rest of this repo, and it's just an HTTP
layer over `core/`/`adapters/claude-code/install.py`, no new logic. Binds
to `127.0.0.1` by default: it serves local file paths and session data
with no authentication, the same trust model as any other localhost dev
dashboard — don't expose `--host 0.0.0.0` on a shared or untrusted network.

## Other agents (Cursor, Codex, ...)

Not implemented yet — see `adapters/cursor/README.md` for the adapter
contract. `core/` has zero Claude-specific code, so a new adapter is a
handful of thin translation scripts, not a rewrite.

## Tests

```
python3 -m unittest discover -s tests -v
```

Stdlib only, no dependencies. See `tests/TEST_PLAN.md` for the full
nominal/edge-case coverage matrix.
