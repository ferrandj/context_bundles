---
name: context-bundle
description: Turn on/off automatic recording of AI coding sessions into replayable JSONL bundles, list recorded bundles, and reload a past bundle's context (prompts + files/URLs it read) into the current session. Use when the user says things like "enable context bundles", "save a bundle of this session", "load the last context bundle", "what bundles do I have", or "/context-bundle".
---

# context-bundle

Static, agent-agnostic session recording. All the real logic (config,
recording, deduplication, replay-plan generation) lives in plain Python 3
stdlib scripts under `core/` and `adapters/claude-code/` in this skill's
parent repo (`context_bundles/`) — this file only tells you, the agent,
which script to run for which request and how to use its output. Never
reimplement the parsing/dedup/config logic inline; always shell out to the
scripts below so behavior stays deterministic and testable.

Resolve `$REPO` as the absolute path to the `context_bundles` repo this
skill was copied/symlinked from (it contains `core/`, `adapters/`,
`tests/`). If you're unsure, look for a `context_bundles` directory
containing a `core/bundle_config.py` file near this skill's own location.

## Parsing the option

The user invokes this skill with an option, either as `/context-bundle
<option> [args...]` or `/context-bundle:<option> [args...]`. Take whatever
argument string you were given, strip a leading `:` if present, and split on
whitespace to get `<option>` and its remaining `[args...]`. If no option was
given, treat it as `status`.

Valid options: `status`, `enable`, `disable`, `set-destination <path>`,
`list`, `load <bundle-id|latest>`.

## `status`

Run:
```
python3 $REPO/core/bundle_config.py status
```
Report enabled/disabled, the destination folder, and bundle count in plain
language.

## `enable`

1. Run `python3 $REPO/core/bundle_config.py status` to check the current
   destination.
2. If `destination` is already set, skip to step 4.
3. If `destination` is null: ask the user, via `AskUserQuestion`, where they
   want session bundles stored (suggest a sensible default like
   `~/context_bundles_data` as one option). Then run:
   ```
   python3 $REPO/core/bundle_config.py set-destination "<their answer>"
   ```
4. Run:
   ```
   python3 $REPO/core/bundle_config.py enable
   python3 $REPO/adapters/claude-code/install.py enable
   ```
5. Tell the user recording is on, where bundles will be written, and that it
   takes effect starting with new sessions (Claude Code loads hooks at
   session start, so the *current* session won't be recorded — only ones
   started after this).

## `disable`

Run:
```
python3 $REPO/adapters/claude-code/install.py disable
python3 $REPO/core/bundle_config.py disable
```
Confirm to the user that recording is off. Existing bundle files are left
untouched.

## `set-destination <path>`

Run:
```
python3 $REPO/core/bundle_config.py set-destination "<path>"
```
Confirm the new destination back to the user.

## `list`

Run:
```
python3 $REPO/core/bundle_list.py
```
Each line is one JSON object (id, filename, size_bytes, line_count,
session_meta with username/root_path/started_at, and an `error` field if
the file couldn't be parsed). Render this as a short table/list, newest
first, flagging any entries with a non-null `error`.

## `load <bundle-id|latest>`

This is the one option that reconstructs context, and it's the one place
where you (the agent) do real work beyond running a script — a script can't
populate your own context window, only you can, by actually calling your
tools. Follow this procedure exactly:

1. Run:
   ```
   python3 $REPO/core/bundle_load.py <bundle-id-or-latest>
   ```
   This is a **read-only, static** operation: it parses the bundle,
   deduplicates operations, and filters down to the ones safe/meaningful to
   redo. It does **not** touch your context by itself. If it prints an
   `"error"` field, report that error and stop (e.g. no destination
   configured, bundle not found).

2. The output has `session_meta`, `prompts` (ordered list of `{"text":...}`),
   `context_operations` (ordered list of `{"operation", "details", "stale"?}`),
   and `stats`.

3. Replay, in order:
   - For every entry in `prompts`, note its text (you'll summarize these,
     not literally re-submit them as new user turns).
   - For every entry in `context_operations`:
     - `operation: "read"` with `stale` false or absent → call your `Read`
       tool on `session_meta.root_path` + `details.path` (or
       `details.path` directly if `details.outside_root` is true).
       If `stale: true`, skip it and note it as unavailable instead.
     - `operation: "glob"` → call your `Glob`/equivalent tool with
       `details.pattern` (and `details.path` if present).
     - `operation: "grep"` → call your `Grep`/equivalent tool with
       `details.pattern` (and `details.path` if present).
     - `operation: "web_fetch"` → call `WebFetch` with `details.url`.
     - `operation: "web_search"` → call `WebSearch` with `details.query`.
   - Skip anything you don't recognize and mention it was skipped, rather
     than guessing.

4. Finish with a short summary: how many prompts were replayed (and what
   they were about, briefly), how many files/URLs/searches were
   successfully re-read, how many were stale/skipped and why, and the
   `stats` counts (total lines, malformed, deduped, excluded) from step 1's
   output.

If recording is currently enabled, these tool calls get logged into the
*current* session's own bundle automatically — nothing extra to do.

## Notes for future adapters

The scripts above only exist for Claude Code
(`adapters/claude-code/`). Other agents need their own thin adapter calling
the same `core/` functions — see `adapters/cursor/README.md` for the
contract. This skill file itself is Claude-Code-specific (it assumes Claude
Code's tool names); a port to another agent would need an equivalent
skill/command file using that agent's own tool names in the `load` step.
