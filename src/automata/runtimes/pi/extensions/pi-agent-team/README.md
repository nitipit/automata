# pi-agent-team

A TypeScript Pi extension that starts and controls independent Pi RPC workers
through their stdin/stdout pipes. No Python kernel, `pi-team` CLI, relay, or
separate worker-manager skill is required. Delegation decisions and result review
remain with the parent agent and user; this extension handles process and message
mechanics, not autonomous scheduling.

## Requirements and loading

Developed against `@earendil-works/pi-coding-agent` **1.4.0**, Node.js 24, and Linux.
The `pi` executable must be on the parent process's PATH. It needs the native RPC
commands and `agent_settled` lifecycle documented by that version. Windows process
group cleanup is not supported or verified by this version.

The bundle has no additional runtime dependencies beyond Node and Pi's provided
`typebox` module. Pi loads its TypeScript directly. For an explicitly authorized
one-session trial, load the source bundle with:

```sh
pi --extension /absolute/path/to/pi-agent-team
```

The repository's `automata pi-extension install` command can install the bundle
by name (`pi-agent-team`) under a separately approved target root. Loading or
installation does **not** start workers. Only an explicit `agent_start` tool call
does that. No installation or live-model trial is implied by the tests below.

## Architecture

```text
parent Pi session
  └── pi-agent-team extension
        ├── worker controller A ↔ Pi RPC process A
        └── worker controller B ↔ Pi RPC process B
```

One controller owns each child's pipes, request IDs, queue snapshot, capture
buffers and report history. Stdout is consumed continuously and framed only on
LF, including across partial chunks and UTF-8 boundaries. Stderr is captured
separately. There is no event-log polling loop.

Workers are independent processes, but controllers run inside the parent Pi
process. Event handling uses no parent model calls. Assigning work and reviewing
reports do use parent turns. This does not give the parent multiple simultaneous
reasoning flows.

## Tools

### `agent_start`

```json
{
  "workerId": "reviewer",
  "cwd": "/absolute/workspace",
  "provider": "approved-provider",
  "model": "exact-approved-model-id",
  "thinking": "off",
  "resources": "inherit"
}
```

Starts an **idle** worker, then queries `get_state`. Provider, exact model ID,
thinking level, and session identity are checked before any assignment. A fuzzy
model match, clamped thinking level, or resumed-session mismatch fails startup;
there is no model fallback. Startup failure attempts owned-process cleanup.

- `workerId`: unique within this extension runtime, including stopped workers.
- `cwd`: absolute existing directory, resolved to its real path.
- `thinking`: `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, or `max`, supported
  by the explicitly selected model.
- `resources`: defaults to `inherit`, using normal Pi resource discovery in that
  workspace. `minimal` disables extensions, MCP, skills and prompt templates;
  context-file discovery and normal Pi settings still apply. It is not a sandbox.
- Optional `sessionId`: resume one **exact**, authorized, inactive session from
  Pi's normal storage. The resulting ID must match. The tool does not scan raw
  session files and does not use "latest session". It rejects the parent session
  and sessions already claimed by another local controller, but cannot detect a
  session opened by another independent Pi process. Confirm inactivity first.

New sessions use Pi's native persistent session storage. Workers use existing
provider credentials and can consume model quota after dispatch. Resource loading
may have its own effects; inherited extensions are trusted executable code. The
extension never adds `--approve` or grants a worker UI confirmation automatically.

The child environment sets `AUTOMATA_AGENT_TEAM_WORKER=1`, so this extension
registers no tools or handlers in the worker. The six manager tools are also
excluded through Pi's CLI. This prevents recursion through this manager, not
arbitrary subprocesses started by worker code or other extensions.

### `agent_send`

```json
{
  "workerId": "reviewer",
  "mode": "prompt",
  "taskId": "auth-review-01",
  "text": "Review the authentication changes. Report findings, paths, tests and remaining uncertainties. Do not modify files."
}
```

- `prompt`: start an assignment on an idle worker; requires a unique `taskId`.
  Effective settings and idle/queue state are checked again before dispatch.
- `steer`: adjust an active assignment.
- `follow_up`: explicitly queue another instruction as part of that same
  assignment. It is not a separate independently reported task.

One assignment is active per worker. A dispatch reservation prevents concurrent
new prompts from racing. Completed or rejected task IDs are not reused within
that controller. Text is limited to 60,000 UTF-8 bytes.

A successful result is an **acceptance receipt, not completion**. Native prompt
`disposition: "handled"` creates a `handled` report rather than waiting forever
for a run that did not start. A timeout or pipe error after dispatch has an
**unknown outcome**: retain the request ID, inspect `agent_status`/`agent_read`,
and never blindly resend. Late responses remain correlated and can resolve an
uncertain request. No automatic retries or restarts are performed.

Cancelling the parent tool before assignment dispatch prevents dispatch. Once
sent, cancelling the parent tool does not undo the assignment; use `agent_abort`
or `agent_stop` deliberately.

### `agent_status`

```json
{"workerId": "reviewer"}
```

Omit `workerId` to list all tracked workers. Returns process state, verified
session/settings, assignment, observed queue contents, pending/uncertain request
IDs, latest report reference, exit facts and capture warnings. It also exposes
notification-capacity errors and historical recovery references from the active
parent branch. Historical references are **not** reattached live workers.

This is a tracked snapshot, not a fresh remote query or a task-success judgment.
Queue text is bounded for inspection; native `queue_update` events are retained
subject to capture limits.

### `agent_read`

Read a report by ID, or omit `reportId` for the latest retained report:

```json
{"workerId": "reviewer", "view": "report", "reportId": "returned-report-id"}
```

Read incremental evidence:

```json
{"workerId": "reviewer", "view": "events", "maxBytes": 16000}
```

Pass the returned `nextCursor` unchanged to continue. The `stderr` view has its
own cursor stream. Cursors are exclusive positions, opaque to callers, scoped to
one worker instance and one stream. Reads do not consume records. An omitted
cursor starts at the oldest retained record; an empty result at the current end
does not mean work finished.

- `gap: true`: the requested position expired; results start at the earliest
  retained position. `earliestCursor` and loss counts make the gap explicit.
- `blocked: true`: the next record does not fit the read budget. Increase
  `maxBytes` to `requiredBytes`; the record has not been skipped.
- Oversize captured records contain a truncation marker and preview, not silent
  replacement with apparently complete evidence.
- A cursor from another worker, another stream, or an invalid future position is
  rejected.

`maxBytes` budgets event/stderr record payloads, excluding the response envelope;
allowed range is 256–131072. Report reads use bounded reports, not cursor paging.
Do not rely on raw capture as permanent storage: it can contain sensitive tool
output and is retained only in this extension runtime.

### `agent_abort`

```json
{"workerId": "reviewer"}
```

Requests native Pi abort and waits for its acknowledgement. Does not kill the
worker, undo external changes, or clear pending instructions. **Native abort can
continue queued steering/follow-up work.** Inspect the observed queue and reports
before reassignment. This first version intentionally exposes no generic RPC or
queue-clearing tool; stop the worker if cancellation of all further processing
is required.

### `agent_stop`

```json
{"workerId": "reviewer"}
```

Closes stdin for native orderly shutdown, then uses bounded TERM/KILL escalation.
On Linux, each worker is launched in an owned process group; escalation targets
that group, including ordinary tool subprocesses. Stop is idempotent. The result
contains the observed worker exit facts; an unconfirmed exit is an error, not a
successful cleanup claim.

Stopping does not delete sessions, artifacts, or undo changes. Descendants that
explicitly detach into other process groups are outside this cleanup guarantee.

## Automatic reports and parent availability

The controller waits for **`agent_settled`**, not merely `agent_end`. Reports
include worker/instance/task/report/session identity, the last finalized assistant
text, provider-error or abort evidence, truncation and capture-loss flags. A
crash before settlement produces an `exited` report. A broken command/output pipe
produces a `failed` report with explicit uncertainty: the worker may still be
running and must be inspected/stopped, not blindly reassigned. Settlement is not
acceptance or proof of task success; the parent must review artifacts and tests.

Completions arriving together are batched. Reports are delivered as labeled
custom messages with `triggerTurn: true` and `deliverAs: "followUp"`, so they
queue behind an active parent run rather than steering it. Idle delivery can
start a parent turn. Routine progress events do not wake the parent.

Worker output is labeled as external agent content, never promoted to system or
user authority. Only one report is produced per assignment, even if settlement
is duplicated. A failed parent submission is not automatically resent because
its acceptance may be uncertain; inspect the retained report instead.

There is no autonomous scheduler or always-thinking parent. Workers continue
while you talk with the parent, but report review and user conversation share
one parent reasoning flow. Collect-only delivery is not part of this version.

## Bounds and lifecycle

Default hard bounds:

| Resource | Bound |
|---|---:|
| Concurrent owned workers | 8 |
| Worker records per parent runtime, including stopped ones | 32 |
| Assignment IDs per worker | 256 |
| Pending plus uncertain RPC requests per worker | 32 |
| RPC response deadline | 30 seconds |
| Each shutdown escalation wait | 1 second |
| Stdout record framing buffer | 8 MiB |
| Event capture per worker | 1 MiB / 2048 records |
| Stderr capture per worker | 256 KiB / 2048 records |
| Retained reports per worker | 32 |
| Report assistant text | 24,000 UTF-8 bytes |
| Automatic notification text per report | 4,000 UTF-8 bytes |
| Reports per notification batch | 8 |
| Pending parent notification batches | 16 |
| Completion backlog awaiting notification | 32 reports |

Capture eviction, record truncation and framing errors are observable. Framing
oversize records are discarded through their next LF, then parsing resumes; an
oversize/missing response may leave a request uncertain. At notification capacity,
reports remain available for explicit inspection subject to report retention.
No automatic task replay is used to recover missing evidence.

Session startup registers no processes. Normal parent shutdown, session switch,
or extension reload stops owned workers and suppresses late report delivery.
Runtime buffers/cursors are then lost. Non-context parent session entries retain
worker identities and shutdown/report references, while delivered custom messages
retain bounded summaries. Use the native worker session for durable history;
raw event capture is not persisted. No worker is silently reattached or resumed.

A parent crash or SIGKILL can bypass lifecycle handlers and leave workers running.
Saved PIDs are historical evidence, **not permission to kill a possibly reused
PID**. Check live identity and inactivity before manual recovery or explicit
session resumption. There is no owner-loss watchdog in this version.

## Verification

From the repository's prepared development environment:

```sh
.venv/bin/python -m pytest \
  tests/integration/automata/extensions/agent_team_test.py \
  tests/integration/automata/install/pi_extensions_test.py
```

The checks use offline subprocess doubles for RPC and the installed Pi loader
for TypeScript extension registration. They do not start model-consuming workers,
prove provider access, or prove end-to-end live parent wake-up. A real two-worker
smoke test requires separate approval of model/thinking/workspaces and quota use.

### Live smoke coverage

One approved trial on **2026-10-22**, using Pi **1.4.0** and
`openai/gpt-6-luna` / `medium` for an isolated RPC parent and two workers, passed:

- Concurrent dispatch of read-only synthetic-fixture assignments, with correct
  results and distinct worker/session/report identities.
- Automatic report delivery waking an idle parent for review, without polling.
- Aborting an active model operation and delivering `aborted: true` evidence.
- Explicit worker stops with exit code 0 and no remaining owned live processes.

This was a single source-loaded trial, not a global installation, repeatability
study, or interactive TUI verification. Abort occurred during model processing,
not an already-running long shell tool. Active-worker reload, abrupt parent loss,
resume and inherited-resource scenarios were not exercised live.
