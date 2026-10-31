# Kernel-owned native Pi RPC

Use this when a persistent kernel helps an agent retain live subprocess state.
It is a workflow, not a replacement RPC SDK or task manager. Native Pi's installed
`docs/rpc.md`, `rpc-commands.md`, `json.md`, `rpc-extension-ui.md` and CLI help own
the version-specific protocol, commands, events and UI limits.

## Prepare only what is missing

Check that the chosen Python environment can import `ipykernel` and
`jupyter_client`, and that the intended Pi executable is usable. Installed software,
a ready authenticated kernel connection and a received coordinator message are
three different readiness facts. Missing dependencies do not authorize installing
them or changing the runtime.

Use a task-owned private directory (0700), connection file (0600), loopback binding
and a fresh nonempty HMAC key. Never print the key or send the connection file in
a notification. Keep kernel identity, connection location, CWD, lifecycle owner
and a bounded handoff lifetime. Correlate Jupyter replies **and idle status** by
`parent_header.msg_id`; disable interactive stdin. One client owns a given
execution's replies. Reconnect to the same kernel for its objects; unrelated
Python invocations do not share them. Generic kernel/process guidance owns launch,
connection-file ownership and shutdown details.

## Launch and retain native objects

For an **approved disposable, tool-free** worker, a kernel cell can create the
native process directly. The variables below are approved inputs, not defaults:

```python
import asyncio

proc = await asyncio.create_subprocess_exec(
    "pi", "--mode", "rpc",
    "--provider", approved_provider, "--model", exact_model_id,
    "--thinking", approved_thinking,
    "--no-session", "--no-extensions", "--no-mcp", "--no-skills",
    "--no-prompt-templates", "--no-context-files", "--no-themes",
    "--no-tools", "--no-approve", "--offline",
    cwd=approved_cwd,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    limit=256 * 1024,
)
```

Check these flags against the installed CLI. They are resource choices, **not**
mandatory team policy or a sandbox: coding workers may need tools, extensions,
context files or persisted sessions. `--offline` suppresses automatic startup
network activity, not an explicitly requested provider call. A new session is not
an authorized resume; use only an exact authorized inactive identity when resuming.

Retain `proc`, pending-response futures, reader tasks, finalized-message evidence
and a result object in that kernel. Before sending a prompt:

- Start **one** stdout coroutine reading bounded byte records through LF only
  (`await proc.stdout.readline()` with an explicit stream limit is suitable).
  Parse JSON after framing; U+2028/U+2029 inside strings are not line boundaries.
  Drain stderr separately and bound its tail; never parse diagnostics as commands.
- Assign a unique native command `id`; register its future before writing one
  JSON object plus `\n`, then `await proc.stdin.drain()`. Match response ID and
  command, not arrival order. Bound pending requests, record size and retained
  results; flag malformed/oversize records or evidence loss rather than hiding it.
- Send native `get_state` and verify actual provider/model/thinking/session before
  paid dispatch. Keep native fields, e.g. `prompt.message`, optional `images` and
  `streamingBehavior`; do not invent a mandatory task-ID or assignment layer.
  Discover models/effort/commands through native APIs when needed and authorized.

A native response can be rejected, or accepted with `started`, `queued` or
`handled` disposition. `handled` means that submitted prompt did not itself start
a run; do not wait for a settlement that was never promised. Extension-triggered
work can still emit its own events. Session events generally lack request IDs;
do not claim one settlement completed every queued prompt. For a small isolated
run, a future installed before dispatch is sufficient correlation; broader work
needs explicit evidence about which activity was observed, not guessed task IDs.

## Observe, store, then notify

The stdout reader continues through responses, finalized messages and events; do
not stop it on `agent_end` or the first report. Retries, recovery, compaction and
queued work can continue until **`agent_settled`**. Capture finalized assistant
text/error and native usage when reported, labeling its coverage. Process exit,
provider failure and transport loss are separate outcomes, not substitutes for
settlement or proof of success. Respect the task's retry/cost envelope.

A minimal event-return sequence is:

1. Before dispatch, register an activity/settlement future and an asynchronous
   observer. The sole reader resolves it from the actual native event. Deduplicate
   the observer for that activity; do not make a second paid prompt to test a lost
   response. Observe unexpected process exit separately with `await proc.wait()`.
2. On settlement, store a typed result in the kernel and persist useful evidence
   in task storage **before** sending a notification. Include observed identity,
   disposition, final text/error, aborted flag, relevant counts and uncertainty.
   Execution settlement, exact-output checks and task acceptance remain distinct.
3. Send a small event/reference through the approved coordinator wake path. For the
   existing **NodalWire 0.2** Pi bridge, use an explicitly known local route/peer,
   matching prepared client/relay, and the actual Pi application **v2** schema.
   With authorized wake-up, options are `triggerTurn:true, deliverAs:"followUp"`.
   Send JSON bytes with `send`, not an NWR1 request envelope. The NodalWire skill's
   external-client reference and active bundle's `protocol.ts` own encoding/bounds.
   If the kernel lacks its Python SDK but an installed Node client is ready, an
   approved tiny kernel-launched send helper can bridge the event; no installation
   or permanent controller is implied. Close its client after the one send.
4. Verify actual coordinator receipt and a correlated **live kernel readback** of
   the stored result. SDK relay acceptance alone proves neither. A finite watchdog
   targeted at the coordinator covers missing evidence; owner-loss coverage needs
   a lifetime independent of the worker/kernel. It is not the normal delivery loop.
   Yield rather than sleep or poll state/files/process lists.

## Uncertain outcomes and cleanup

Timeout, cancelled Jupyter execution or cancelled client wait may leave native
work running. Inspect owned handles and correlated evidence before repeating an
operation; do not automatically reconnect, restart or replay. A late response is
still evidence. Headless UI limitations never authorize automatic approval;
cancel/report unsupported dialogs instead of bypassing permission safeguards.

Native `abort` does **not** clear queued instructions and can continue them.
`clear_queue` is a separate explicit action returning queued text, not an automatic
side effect. Native session transitions can be cancelled; inspect effective state
after deliberate session/model changes before trusting an old snapshot. Do not
attach two owners to the same live session or take another controller's pipes.

Retain a kernel only for an approved, bounded readback period. Preserve durable
results, close owned Pi stdin for orderly shutdown, await exit, and finish/cancel
owned reader/notifier tasks as appropriate. Escalate only against verified owned
processes if graceful shutdown fails. Request Jupyter shutdown, confirm its reply
and process exit; a saved PID alone cannot justify signalling a reused process.
Live objects are lost on kernel restart and never replace durable evidence.
