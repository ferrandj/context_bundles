# Test plan

Run everything:

```
cd context_bundles
python3 -m unittest discover -s tests -v
```

No external dependencies — stdlib `unittest` only. Every test isolates
itself from the real machine state via `CONTEXT_BUNDLES_HOME` (overrides
where config/state live, see `core/paths.py`) and/or `tempfile.TemporaryDirectory`
for bundle destinations and fake `settings.json` files. Nothing in this
suite touches `~/.context_bundles` or `~/.claude/settings.json` on the
machine running it.

## Coverage matrix

| Area | File | Nominal | Edge cases covered |
|---|---|---|---|
| Filename generation | `test_bundle_writer.py` | Matches `YY-MM-DD_HH-MM-SS_<uuid4>.jsonl` | Two calls at the same timestamp still produce distinct names |
| Path relativization | `test_bundle_writer.py` | Path under root → relative | Path outside root → absolute + flagged; root path itself → `.` |
| Session meta line | `test_bundle_writer.py` | Correct flat keys, written once | Second `write_session_meta` call on same file is a no-op (idempotent) |
| Appending operations | `test_bundle_writer.py` | One JSON line per call, correct shape | — |
| Reading bundle lines | `test_bundle_writer.py` | Parses valid lines | Malformed line yields `None` instead of raising; blank lines skipped; missing file → `None` meta |
| Session state pointer | `test_session_state.py` | Set/get/clear round-trip | Unknown session → `None`; malicious session_id sanitized (no path traversal); stale (>24h) pointers swept; corrupt pointer files swept; missing state dir → 0 removed |
| Config | `test_bundle_config.py` | Get/set destination, enable/disable | Missing config file → defaults; corrupt config file → defaults (doesn't crash); `status` bundle count; unknown/absent CLI command → exit code 2 |
| Bundle listing | `test_bundle_list.py` | Lists `.jsonl` files with parsed meta, newest first | Empty/missing/`None` destination → `[]`; non-`.jsonl` files ignored; malformed meta line → `error` set, doesn't crash; empty file → `"empty file"` error |
| Bundle load / replay plan | `test_bundle_load.py` | Filters to `prompt`+read-type ops, in order | Malformed line counted & skipped; bundle with only prompts → empty `context_operations`; duplicate reads deduplicated (order preserved); stale-path flag true/false based on real filesystem state; `latest` resolves to newest filename; missing bundle id → `FileNotFoundError` / CLI exit 1 |
| Tool → operation mapping | `test_tool_operation_map.py` | Every mapped tool (`Read`, `Write`, `Edit`, `NotebookEdit`, `Bash`, `Grep`, `Glob`, `WebSearch`, `WebFetch`, `AskUserQuestion`, `Agent`, `Skill`, `mcp__*`) | Unknown tool → `other` with raw name preserved; missing expected input key → empty details instead of crashing; no root_path supplied → raw path kept |
| Hook scripts (subprocess, real stdin/stdout contract) | `test_hooks_integration.py` | SessionStart creates bundle + meta line + pointer; UserPromptSubmit/PostToolUse append correctly; SessionEnd clears pointer but keeps the file | Disabled config → hooks are no-ops; enabled with no destination → `SessionStart` emits an ask-the-user message and creates nothing; no active bundle for a session_id → silent no-op; missing `tool_name` → no-op |
| Hook installation | `test_install_hooks.py` | `enable` adds all 4 events to a settings.json (creating the file if absent) | Preserves unrelated settings keys and unrelated existing hook entries; `enable` run twice doesn't duplicate; `disable` removes only our entries and drops now-empty event keys; `disable` on a file that was never enabled is a no-op; `status` reports which events are currently installed |
| Performance | `test_performance.py` | 5,000-line bundle parses in well under a second on any reasonable machine | — |

## Manual verification (not automated — see plan's Verification section)

1. Invoke each hook script by hand with `echo '<json>' \| python3 adapters/claude-code/hook_x.py` and inspect the resulting file.
2. Walk the `context-bundle` skill's `enable` → `status` → `list` → `load latest` → `disable` sequence against a scratch destination.
3. Build a bundle by hand, run `core/bundle_load.py`, and manually replay it via the skill's `load` instructions to confirm the reconstructed summary matches what the bundle recorded.
