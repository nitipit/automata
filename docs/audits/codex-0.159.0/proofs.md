# Reproducible proofs and evidence boundaries

## Native offline check

The scripts in `tests/integration/automata/codex_runtime/` are opt-in audit probes,
not automatically launched by pytest and not production adapters. Requirements:
Linux bubblewrap with unprivileged namespaces, Python 3.12+, and the already
installed **native** Codex executable. Do not download/build Codex to run them.

```sh
codex --version
codex app-server generate-json-schema --help

# Use a new task-owned root; the script refuses an existing directory.
python tests/integration/automata/codex_runtime/offline_probe.py \
  --binary "$NATIVE_CODEX" --state-root "$TASK_ROOT/test-state/native"
python tests/integration/automata/codex_runtime/verify_probe.py \
  "$TASK_ROOT/test-state/native"
```

The installed launcher in this environment is a pnpm Node shim; native executable
was resolved under its own `@openai/codex/vendor/x86_64-unknown-linux-musl/bin/`
package, without inspecting user Codex config/auth. `codex --version` was 0.159.0.

The process boundary mounts only system binaries/libraries, a fresh task-owned
`/probe`, and the installed native executable. It unshares all namespaces,
including network, has empty `/etc` and no host home, clears environment variables,
uses `/probe/home` and `/probe/codex`, and talks only through owned stdio. No real
project ancestors, user session store, sockets, credentials or remote daemon are
visible. Read-only model sandbox and on-request approvals remain configured;
no bypass flags are used. Shutdown closes stdin, waits boundedly, and terminates
only the owned process group if required. Both observed runs exited 0 normally;
stderr was empty. No processes were left running.

This isolation matters: app-server source starts a model catalog worker using
`RefreshStrategy::Online`, even without a submitted model turn. `CODEX_HOME` alone
is not a network sandbox. A worktree nested under the manager project alone would
also permit parent skill/config discovery. Bubblewrap removes both confounders.

The probe's hard RPC allowlist excludes `turn/start`, `thread/compact/start`,
queue start, shell commands and live account methods. It sends only fixed
history fixtures, metadata/discovery requests and idle settings changes. The
candidate Python installer/exporter runs outside the child only into the new
state root; the native loader sees those copies, not global skills.

### Assertions and results

`verify_probe.py` checked the second run (native-2), producing
[native-summary.json](native-summary.json):

- All 40 installed candidate skill names discovered, no skill parser errors.
- Repo/global same-name fixtures both present; alias symlink deduplicated by path.
- Candidate exported Agent Plugins v1 manifest recognized, one namespaced skill;
  packaged timer **not** registered as MCP. Package remained uninstalled/disabled.
- Dynamic function tool definition accepted and persisted in parent/fork metadata.
  No model invocation or tool execution was attempted.
- Hook definition listed as untrusted and command marker absent. This is negative
  trust evidence only; no trusted hook was executed.
- Developer injection accepted without a turn; sentinel persisted in parent
  history while visible turn list stayed empty.
- Same-ID resume accepted. New-ID fork recorded parent linkage; history-only
  developer sentinel absent in child. No completed-turn continuity claim.
- Invalid effort accepted and returned on resume. This is a negative validator
  finding, **not** proof of model support or effective execution.
- No token usage records, no live model requests, exit 0.

Task-owned raw `results.json`, `protocol.json`, isolated Codex histories, schema
output, and source checkout remain with CX-001 evidence outside tracked source.
Only their bounded nonsensitive summary is committed. Those are synthetic probe
histories, not user conversations. The summary deliberately omits transient IDs.

## Local schema evidence

Generated using the installed binary, with fresh HOME/CODEX_HOME and no credentials:

```sh
env -i PATH="$PATH" HOME="$TASK_ROOT/test-state/schema-home" \
  CODEX_HOME="$TASK_ROOT/test-state/schema-home" \
  codex app-server generate-json-schema --experimental \
  --out "$TASK_ROOT/evidence/schema"
```

This generation is not a running app-server protocol or behavioral trial. Inspect
these files in that output:

| Schema | Decision evidence |
| --- | --- |
| `v2/ThreadTokenUsageUpdatedNotification.json` | last/total/window and six usage categories including cache writes |
| `v2/ThreadStartParams.json` | dynamic tools registration input |
| `v2/ThreadInjectItemsParams.json` | raw model-visible history items, not request-local projection |
| `v2/ThreadSettingsUpdateParams.json` | subsequent-turn effort; effort is nonempty string, not supported-model enum |
| `v2/TurnSettingsUpdateParams.json` | active-turn publication, distinct from future thread defaults |
| `v2/ModelListResponse.json` (`Model` definition) | supported reasoning effort options |
| `v2/ThreadCompactStartParams.json` | threadId only; no Pi summary-model/effort/instructions/resume contract |
| `v2/ThreadForkParams.json`, `ThreadResumeParams.json` | native session primitives, not Pi copy/trash guarantees |

## Version-pinned upstream source evidence

Public source was inspected, not built or executed. Tag `rust-v0.159.0` resolves
to commit `687a119f0fcaace47e1f1abcc77cec6c813fd6da`.
Base URL for every source path below:

<https://github.com/openai/codex/tree/687a119f0fcaace47e1f1abcc77cec6c813fd6da/codex-rs>

| Path / anchor | Evidence |
| --- | --- |
| `app-server/src/models_refresh_worker.rs:30–59` | startup background Online catalog refresh |
| `ext/skills/src/host_roots.rs:48–122`; `host_roots_tests.rs:598` | root discovery and dedupe paths, not names |
| `core/src/agents_md.rs:1–17,43–47,64–66` | root-bounded chain, override filename and untrusted project handling |
| `core-plugins/src/manifest.rs:158–194,265–278` | portable manifest plus optional Codex overlay |
| `core/src/context/hook_additional_context.rs` | developer role for hook context |
| `core/src/hook_runtime.rs:849–873` | hook developer messages recorded in conversation |
| `core/src/codex_thread.rs:751–798` | inject API records history without run_turn |
| `app-server/src/request_processors/turn_processor.rs:974–1004` | inject validation and thread ownership/input gate |
| `protocol/src/protocol.rs:2241–2280,2421–2474` | usage fields, noncached/blended totals and context percentage semantics |
| `codex-api/src/sse/responses.rs:116–150` | provider usage conversion, absent details defaulting |
| `core/src/compact.rs:821`; `core/src/session/mod.rs:4752–4864` | compaction uses token accounting; separate response records and context recomputation |
| `app-server/src/request_processors/token_usage_replay.rs` | replayed usage on resume is not a new response |
| `app-server-protocol/src/protocol/common.rs:685,1038`; `v2/thread.rs:145` | experimental settings APIs and dynamicTools field |
| `app-server-protocol/src/protocol/v2/turn.rs:41–91`; `v2/model.rs:130` | captured-step limits; supported effort metadata |
| `tui/src/session_queue_commands.rs:27–145` | queue shared-server safety, exact UUID fast path, enqueue receipt only |
| `ext/image-generation/src/lib.rs:8` | native image_gen namespace; not the Pi codex_imagegen bridge |
| `hooks/src/events/stop.rs:28–39` | stop payload has session/turn/model/transcript/last text, no usage counter |

These internal Rust extension-contributor APIs are not an external Python/JS
plugin loading contract. Their existence does not justify building a custom Codex.

## Public documentation (moving sources)

Checked alongside, not substituted for, local 0.159.0 evidence:

- <https://developers.openai.com/codex/skills>
- <https://developers.openai.com/codex/guides/agents-md>
- <https://developers.openai.com/codex/hooks>
- <https://developers.openai.com/codex/mcp>
- <https://developers.openai.com/codex/app-server>
- <https://developers.openai.com/codex/plugins/build>

Hooks docs describe trust hashes, event-specific additionalContext, async safe
boundaries/no idle wakeup, and unstable transcript format. Plugin docs currently
redirect to cross-surface OpenAI packaging guidance; Codex compatibility claims
here additionally use its pinned loader and native probe, **not** ChatGPT/Agents
API capabilities. MCP documentation is support evidence, not a tested Automata
MCP adapter.

## Focused regression checks

```sh
PI_TEST_PACKAGE_ROOT="$INSTALLED_PI_0871" uv run --offline pytest \
  tests/unit/automata/plugin tests/cli/automata/cli_test.py \
  tests/unit/automata/install/skills_test.py \
  tests/unit/automata/install/pi_extensions_test.py \
  tests/integration/automata/extensions/token_awareness_test.py \
  tests/integration/automata/extensions/message_timestamps_test.py -q
uv run --offline ruff check tests/integration/automata/codex_runtime
```

Result: **47 passed**, Ruff clean, inventory 40/40 names matched, summary JSON
valid. The initial Pi token test auto-selected an older cached Pi 0.85.1 package
and failed because `buildSessionProjection`/`appendUsage` were absent. Explicitly
selecting the current installed Pi 0.87.1 through the test's existing override
resolved that environment mismatch; no Pi implementation/test was modified.
This illustrates why runtime selection must be pinned, not inferred from a
lexically sorted package-cache path. Dependencies were prepared from cache with
`uv --offline` in this checkout's `.venv`; no downloads or global installs.

## Unproven / deliberately not run

No paid or live model call; no native CLI agent behavior trial; no positive trusted
hook delivery; no actual dynamic-tool model dispatch; no MCP server integration;
no UI `/hooks` trust flow; no resume after process restart; no completed-turn
fork/compact continuity; no usage stream from a model; no timer/browser/LINE or
router messages through Codex. No global install, daemon attachment, credential
access, user conversation discovery, own Codex build or production adapter.
