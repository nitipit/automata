# Thin Pi RPC interface

`pi_team.py` is a standard-library, Linux `/proc` CLI for persistent Pi RPC I/O.
It creates **one idle worker**, forwards commands, captures raw records and stops
owned processes explicitly. It does not manage teams, assign work, select final
results, interpret `stopReason`, classify task success or stop at `agent_settled`.
Automata owns all those decisions. No NodalWire dependency, callback, relay setup,
automatic retry setting, deadline, restart or owner-loss watchdog is imposed.

## Interface

```sh
python .agents/tools/pi-team/pi_team.py --help
python .agents/tools/pi-team/pi_team.py create --spec /task/worker.json
python .agents/tools/pi-team/pi_team.py status --worker /task/worker-001
python .agents/tools/pi-team/pi_team.py rpc --worker /task/worker-001 --command /task/command.json --timeout 30
python .agents/tools/pi-team/pi_team.py events --worker /task/worker-001 --cursor 0 --limit 100 --max-bytes 1048576
python .agents/tools/pi-team/pi_team.py stop --worker /task/worker-001
```

Outputs are one compact JSON object. `rpc` stdout is the original correlated Pi
response (unknown fields preserved), including `success:false`; that is not a CLI
transport failure. Exit 1 / `transport_error` means a mechanical problem, not a task
classification. Content is only emitted by explicit `rpc` and `events` requests.
`status` contains process/storage facts, **not Pi session state**; use raw
`{"type":"get_state"}` for session state.

Version-2 spec (numbers below are an **explicit example**, not defaults):

```json
{
  "version": 2,
  "run_dir": "/absolute/task/worker-001",
  "cwd": "/absolute/project",
  "provider": "openai",
  "model": "gpt-6.1-sol",
  "thinking": "medium",
  "resources": ["--no-approve", "--offline", "--no-mcp"],
  "persist_session": true,
  "storage": {
    "segment_bytes": 1048576,
    "max_segments": 8,
    "max_record_bytes": 131072,
    "max_read_bytes": 2097152,
    "max_read_records": 1000
  },
  "startup_timeout_seconds": 30,
  "shutdown_grace_seconds": 5,
  "pi_command": ["pi"]
}
```

`run_dir` must be new, absolute and outside installed tool code. Provider, model,
thinking, resources, persistence and all storage limits are mandatory. Only startup
and explicit-stop grace have defaults (30s and 5s). `pi_command` defaults to `["pi"]`;
it is an explicitly trusted executable prefix, useful for deterministic fakes too.
The tool adds `--mode rpc`, provider/model/thinking and owned session flags, with no
initial prompt. Effective settings and fresh idle state are verified via get_state.
Create returns process facts; check `status:"open"` and startup errors before use.
A create wait expiry is uncertain startup, not permission to create a duplicate.

`resources` explicitly controls inheritance. `[]` retains Pi's normal discovery and
settings; it is not an isolation claim. Supported switches are `--no-extensions`,
`--no-mcp`, `--no-skills`, `--no-prompt-templates`, `--no-themes`,
`--no-context-files`, `--approve`, `--no-approve`, `--offline`, `--no-tools`,
`--no-builtin-tools`. Supported argument/value pairs are `--extension`, `--skill`,
`--prompt-template`, `--theme`, `--tools`, `--exclude-tools`, `--system-prompt`,
`--append-system-prompt`, `--name`. No install or implicit project trust change.
Global Pi settings (including its provider auto-retry policy) remain unchanged.

## RPC commands and ambiguity

Write an original Pi command object to the command file, for example:

```json
{"id":"assignment-1","type":"prompt","message":"Review the approved change"}
```

Use the same worker for later `prompt`, `steer`, `follow_up`, `abort`, inspection and
session commands. Prompt dispositions started/queued/handled describe acceptance,
not completion. Events are uninterpreted; only the agent decides whether to wait,
accept output, send more commands or explicitly stop.

The tool preserves supplied string IDs and generates an ID if absent. It correlates
responses by ID, not arrival order. **Callers must use unique command IDs.** Only
in-flight and ambiguous IDs are remembered (maximum 128 total); known duplicate
IDs and new requests over that bound are rejected before sending. Late responses
clear ambiguous slots and are captured. Completed-ID history is not retained, so
reuse of a completed ID is not detected. There is no unbounded lifetime-ID ledger.

Timeout, disconnect or write failure after possible dispatch means **unknown
outcome**. The tool never retries/resends. Inspect events for the response using
its request ID, respecting retention expiration. Do not resend to discover what
happened. A client disconnect does not cancel a request already dispatched. Control
connections and pending requests are bounded at 128; idle control reads time out.

`extension_ui_response` requires the existing dialog ID and `--send-only`. It has
no ordinary Pi acknowledgement. The result `transport:"stdin_drained"` only means
local pipe drainage, explicitly `pi_acknowledgement:false`; do not wait for a normal
response. Send-only is restricted to this subprotocol.

## Raw capture, bounds and loss

`events` includes **all captured stdout records, including command responses**,
plus tagged stderr chunks. Each entry has metadata `cursor`, `stream`, `time` and
`raw`. For stdout, `raw` is the complete original JSON text (including whitespace,
unknown fields and Unicode), without LF. Parse it as JSON if needed. For stderr,
`raw` is reversible hexadecimal bytes; stderr is never treated as RPC. LF alone
frames stdout; U+2028/U+2029 are not separators. Both pipes are drained continuously.

Cursors are monotonic exclusive positions: pass the returned `cursor` to the next
read. `earliest_cursor`, `next_cursor` (next position to allocate) and `gap` expose
retention expiration/capture gaps. A gap never means success. `blocked` gives the
next record cursor and required encoded bytes when count/byte budgets block a
read; no oversized record is silently skipped. Increase the read budget within
configured ceilings to consume it. Reads return at most the requested records and
sum of encoded log-frame bytes; the compact metadata envelope is additional.

All limits are explicit. Implementation ceilings: segment 64MiB, segments 1024,
record 8MiB, read 16MiB, records/read 10,000. A segment must fit worst-case JSON
escaping of one source frame: `segment_bytes >= 6 * max_record_bytes + 1024`.
The configured `max_read_bytes` must also meet that bound, so every retained
record can actually be retrieved (the joint read ceiling further constrains record
size). Oversize is reported as soon as the framing buffer exceeds its limit, even
if no LF has arrived yet. Actual encoded segments, including the active segment, never exceed
`segment_bytes * max_segments`. Eviction happens before opening a replacement.
Stdout and stderr **share** this budget. No separate unbounded stderr/controller
log: controller stdout/stderr use DEVNULL; compact failures go to private state.
In-memory stdout framing is bounded by max_record_bytes plus a 64KiB read chunk;
control input has a 64MiB hard limit. No full-history in-memory list is retained.

Oversized stdout is drained through LF, not partially recorded; explicit
`capture_error:"oversized_record"`, loss counts/bytes and a cursor gap disclose
that the complete record is unavailable. Invalid JSON, an empty frame, or EOF with
an incomplete stdout frame also creates visible loss. Storage I/O failure latches
`storage_io_error`; further capture is discarded with visible loss accounting while
pipe drainage continues. Short disk writes are explicit partial-frame failures;
state-write failure is reported as `state_error` and must not stop pipe drainage. **No automatic stop follows capture loss.** Pending calls
without a correlated reply receive an immediate capture-loss/unknown-outcome
transport error. If a correlated response is available, its original JSON remains
stdout and current capture-error facts are separately printed to stderr. Always
inspect stderr/status/events after capture errors; a raw response does not certify
complete retained evidence. Capture errors remain visible even if later frames fit.

Offline events reads after controller exit preserve complete stored frames, report
`partial_tail` for an incomplete final log frame, and disclose saved capture facts.
They do not rewrite damaged artifacts or restart the controller. Normal retention
can expire a late response before inspection: choose limits for the approved task.

## Process ownership and explicit stop

Private run directories and socket directories use mode 0700, files 0600. A short
private Unix socket directory under the system temp directory avoids Unix pathname
limits; its path is in private state. No external port, general broker or network
service is started. Run spec/state, birth lease and capture remain in the task run.
Atomic state writes retain Linux boot ID/start ticks/process-group identities.
Stop closes stdin, waits the configured grace, then birth-verifies owned TERM/KILL
as needed, including anchored descendants. It does not send an implicit abort or
claim task acceptance. Inspect shutdown facts; `unconfirmed` is not cleanup success.

No automatic owner-loss/deadline policy exists. Controller process loss closes its
pipes (an unavoidable I/O failure that may make Pi exit), but does not authorize a
restart, reassignment or task classification. Status reports controller unavailable.
Explicit stop can clean orphan groups using private birth leases and ownership
tokens; stale/reused PIDs are not ownership. A suspended/unreachable controller is
signaled only by explicit stop. After stop, the short socket directory is removed;
artifacts and sessions are not deleted.

Pi session JSONL retention is **separate**. With `persist_session:true`, sessions
live under the run's `sessions/`; with false, Pi uses `--no-session`. Session files,
user-created files and Pi tool artifacts are not part of bounded capture storage.
The tool does not scan or prune raw Pi session files and does not claim total worker
disk usage is bounded. Clean up task artifacts only with their owner's approval.

## Migration and packaging

Version-1 `start/watch/results`, batch worker/prompt specs, mandatory callbacks and
semantic task outcomes are removed. Old specs fail with version-2 migration advice;
old run artifacts are never silently transformed. Explicitly create workers, issue
Pi commands, consume raw events, interpret work, and stop workers. Existing live
version-1 processes must be managed with their matching old interface.

The installed tool is a directory copy and requires no repository imports or new
Python dependencies. Run with an existing prepared Python and current Pi RPC.
Nothing installs dependencies, changes global settings or launches a model trial.
Tests use `tests/fixtures/pi_team/fake_worker.py`, not paid model prompts.
