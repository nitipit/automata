# Pi team

Small Python CLI for an explicitly approved, flat team of fresh Pi RPC workers.
It automates launch/readiness/collection/shutdown, not team design or acceptance.
No model selection, automatic restart, recursion, resumption, worktrees, other
runtimes, relay setup or artifact deletion. All output is JSON; watch emits JSONL.

## Prerequisites and invocation

- Linux with readable `/proc` process birth identities.
- Current `pi` executable supporting RPC `get_state`, prompt dispositions and
  `agent_settled` (implemented against Pi 1.3.0; fake tests are not a live trial).
- Published Python `nodalwire` in the interpreter used to run this script, including
  its native transport dependencies; an already-running trusted-loopback relay.
- Coordinator with an already connected receiving integration, for example the
  maintained Automata Pi NodalWire extension. Names are routes, not identities.

Use a prepared Python environment; installation remains a separate, explicit
operation. No mandatory dependency is added to Automata's core environment.
Missing prerequisites fail before workers launch. The tool never starts a relay.
A non-model readiness inspection is `pi --help` plus importing `nodalwire` in the
selected interpreter; authentication readiness is a separate operator concern.

```sh
/path/to/prepared/python .agents/tools/pi-team/pi_team.py --help
/path/to/prepared/python .agents/tools/pi-team/pi_team.py start --spec /task/team.json
python .agents/tools/pi-team/pi_team.py status --run /task/run-001
python .agents/tools/pi-team/pi_team.py watch --run /task/run-001
python .agents/tools/pi-team/pi_team.py results --run /task/run-001
python .agents/tools/pi-team/pi_team.py results --run /task/run-001 --full
python .agents/tools/pi-team/pi_team.py stop --run /task/run-001
```

The first command is a detached launch, not task completion. `status`, `watch`,
`results` and `stop` require only stdlib Python and make no model calls. Watch is
read-only: Ctrl-C exits with 130 and never stops workers. Stop records a request;
confirm terminal status and `shutdown: confirmed` rather than treating it as an
immediate shutdown receipt. Commands return 0 on successful inspection/request,
1 on invocation/preflight failure. A failed team is reported in the JSON status,
not the inspection command's exit code. Do not retry an uncertain start: inspect
its explicit run directory first. Reusing any existing run directory is refused.

## Version-1 spec

```json
{
  "version": 1,
  "run_dir": "/absolute/task/run-001",
  "deadline_seconds": 3600,
  "startup_timeout_seconds": 30,
  "shutdown_grace_seconds": 5,
  "callback": {
    "endpoint": "tcp://127.0.0.1:5555",
    "name": "team-001-supervisor",
    "recipient": "team-001-manager",
    "timeout_seconds": 15
  },
  "workers": [
    {
      "id": "implementer",
      "prompt": "Perform the approved assignment in /absolute/task/brief.md.",
      "cwd": "/absolute/project",
      "provider": "explicit-provider",
      "model": "explicit-exact-model-id",
      "thinking": "medium"
    }
  ]
}
```

All worker fields are required. IDs are unique ASCII letters/digits/underscore/
hyphen (1–64 characters); 1–32 workers are supported. CWD must be absolute and
exist. Deadline is positive and at most 86400 seconds from launch, including
callback/readiness. Startup command-response timeout defaults to 30 seconds
(max 600); shutdown grace defaults to 5 (max 60); callback timeout defaults to 15
(max 120). Values must be finite positive numbers. Enforcement uses a persisted
same-boot monotonic deadline; wall-clock timestamps are display receipts.
Thinking is an explicit Pi
level, from `off` through `max`; unsupported/clamped effective levels fail rather
than silently substituting. Unknown spec/worker/callback fields are rejected.

Optional `pi_command` is an argv prefix, default `["pi"]`. It permits an explicitly
prepared executable or wrapper (and fake executable tests), not shell evaluation.
It is trusted execution configuration with the same authority as running Pi.
The tool appends `--mode rpc --provider ... --model ... --thinking ...`, an owned
session directory, unique session ID, `--no-approve --offline`. No secrets should
be placed in the command line. Default project-local trust is disabled; any
additional resource/trust flags must be deliberately provided in a prepared
wrapper. Global user resources and environment still apply. This is not a sandbox.

`run_dir` must be a new absolute directory outside this installed tool. The tool
creates it mode 0700 with private files (umask 077); parent-directory permissions,
shared filesystems, disk space and retention remain the caller's responsibility.
Do not place run data under source/installed assets or commit private artifacts.

## Verified callbacks

The existing Pi integration admits only this outer UTF-8 NodalWire envelope:

```json
{"version":1,"type":"message","text":"<JSON-encoded pi_team object>"}
```

The supervisor connects using `callback.name` and sends this object in `text`:

```json
{"version":1,"type":"pi_team_probe","run_dir":"/absolute/task/run-001","nonce":"unique-nonce","reply_to":"team-001-supervisor"}
```

The named coordinator must confirm it is the approved run and reply with this
JSON in message text, through its existing NodalWire integration:

```json
{"version":1,"type":"pi_team_probe_ack","nonce":"unique-nonce"}
```

In Pi, call `nodalwire_send` with `to` equal to the approved `callback.name` and
`text` equal to that ACK JSON string; the tool adds the outer envelope. The sender
must match `callback.recipient`. Receipt and return-path verification is required
before spawning/dispatch; queue acceptance alone cannot satisfy the gate. Native
callback tests use fake transport, not paid automatic coordinator wakeups.

On terminal completion/failure, a `pi_team_result` text object includes version,
run ID/path and status. The independent watchdog sends a failure notice on owner
death/deadline fallback. Notification state is `pending`, `attempting`,
`relay_accepted` or `uncertain`; it is not proof of coordinator handling. Neither
supervisor nor watchdog retries an ambiguous send; watchdog does not resend a
supervisor notification already marked attempting/accepted/uncertain. If a probe
fails, no prompts are dispatched. If relay admission itself fails, local status
and watchdog artifacts may be the only available evidence. No relay can guarantee
delivery after machine death, relay death or simultaneous supervisor/watchdog death.

## Lifecycle and evidence

A detached supervisor owns concurrent workers. A separately launched, bounded
watchdog publishes a birth-identity readiness receipt before worker launch and
checks owner identity, deadline and explicit stop requests without model calls.
A suspended/unresponsive owner cannot defer a stop until a long task deadline.
The supervisor also stops if
its watchdog disappears; launch alone is not watchdog readiness. Tiny exec launchers publish worker birth leases before exec; these
allow fallback collection even if the supervisor dies before saving spawn state.
All effective settings must match before **any** prompt is dispatched: provider,
exact model, thinking, fresh idle state, session ID and task-owned session path.
Automatic provider retries are explicitly disabled. Every command has a unique
ID; the stream listeners are installed before prompting.

A successful prompt response means only accepted. The tool requires disposition
`started`, then `agent_settled` plus final assistant evidence. `agent_end` alone
is not completion. Aborted, error, length, toolUse/unknown final stop reasons,
missing settled/message evidence, broken streams and startup mismatch fail
conservatively. Assistant errors remain in private logs, not compact views.

State progresses through `starting`, `running`, `stopping`, then `succeeded`,
`failed`, `stopped` or `timed_out`. Graceful shutdown sends abort and closes stdin,
then escalates through identity-verified process-group SIGTERM/SIGKILL with bounded
grace. The watchdog permits the complete bounded escalation budget before killing
a nonresponsive spawner and collecting its final worker leases. Verified group
members or inherited per-worker ownership markers anchor
descendant cleanup after leader exit.
Unconfirmed shutdown is never reported as success. Watchdog evidence overlays
stale supervisor state in status; `supervisor_alive` distinguishes stale metadata.
Timing receipts separate callback connection and probe/ACK (including failure
attempts) from team startup, per-worker spawn/readiness, acceptance, execution,
shutdown and total supervisor duration. Worker readiness and execution durations
are cumulative from their respective phase starts, not additive subphase totals.

Artifacts (retained, never automatically deleted):

| Path | Contents |
| --- | --- |
| `spec.json` | Private normalized spec, including full prompts |
| `state.json` | Atomic supervisor state and effective/session identities |
| `events.jsonl` | Compact phase events, no prompts/tool args |
| `workers/ID.rpc.jsonl` | Full raw RPC output (private content/tool args) |
| `workers/ID.stderr.log` | Raw diagnostics, private and untrusted |
| `workers/ID.result.json` | Final assistant message, including detailed result |
| `workers/ID.lease.json` | Worker process birth identity and inherited ownership marker |
| `sessions/ID/` | Persistent Pi session artifacts |
| `supervise.log`, `watchdog.log` | Supervisor/watchdog diagnostics |
| `watchdog-ready.json` | Independent watchdog birth-identity readiness receipt |
| `watchdog.json` | Independent completion/fallback evidence |
| `stop-request.json` | Explicit stop/deadline request, when present |

Compact status/results use allowlisted fields and exclude prompt/message/tool
content. `--full` deliberately emits assistant result content and the artifact
root; read raw logs explicitly only when appropriate. Logs are continuously
drained to disk, not accumulated in memory; provision disk space for verbose
workers. RPC records above 16 MiB or malformed framing fail conservatively.

## Engineering choice and limits

Installed pi-rpc v0.19.0 was assessed: its public `start` surface accepts only
CWD/name/pi-bin and uses global broker state. Explicit launch settings, run-owned
artifacts, lifecycle IDs and watchdog ownership would need wrapper/private broker
plumbing. This tool instead uses stdlib asyncio subprocess RPC directly; it does
not implement a general reusable broker or supervision framework.

Source/fake tests establish protocol/lifecycle/privacy boundaries, not real-model
correctness, provider credentials, arbitrary extensions or live delivery reliability.
A worker can perform authorized external effects before a failure; stopping does
not roll them back. Process groups and trusted-local names are cooperative
ownership safeguards, not security isolation against hostile workers. Never infer
a successful deliverable from lifecycle status alone.
