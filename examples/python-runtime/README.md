# Python live workspace

A separate local prototype: the browser and an external Python driver work on
**the same `counter` object in one persistent ipykernel**. No integration with
Automata's normal Python execution is implied.

## Run

Requires uv, Deno, and this repository checkout. From `examples/python-runtime/`:

```sh
uv sync --locked
deno install --allow-scripts=npm:esbuild
deno task build
uv run uvicorn server:app --host 127.0.0.1 --port 8021
```

Open **http://127.0.0.1:8021/**. Use Add/Subtract or set an integer. The page shows
connection/busy state, kernel generation, Python object identity and a bounded
source-labelled event log. Stop the server with Ctrl+C: it shuts down its kernel
and removes its owned Unix socket. Do not use multiple workers or `--reload`.
For another port, set `WORKSPACE_PORT` to the same value as `--port`.
For an isolated instance, set `WORKSPACE_RUN_DIR` to its own private directory;
use `driver.py --socket /that/directory/agent.sock` to target it.

Only `/`, generated `/assets/`, `/action` and `/events` are browser-accessible.
Python sources, `.run/`, tests and repository files are not served. The build
reuses Adaptive UI Base/Button/Card and repository-local library sources;
building trusts those local sources and esbuild. No source maps are emitted.

## Agent / external Python driver

In a **different terminal**, still from this example directory:

```sh
uv run python driver.py execute 'saved_counter = counter; counter.value += 10'
uv run python driver.py execute 'assert saved_counter is counter; print(id(counter)); counter.value += 1'
uv run python driver.py status
```

These are independent CLI processes, but `saved_counter`, `counter` and their
identity persist in the server's kernel. Watch the browser update. Browser
changes are immediately visible to the next Python call:

```sh
uv run python driver.py execute 'print(counter.value)'
```

`driver.py` accepts multiline code with `execute -` (driver stdin only), or an
explicit socket path with `--socket`. The importable
`await driver.request({"command": "execute", "code": "...", "timeout": 10})`
returns the same JSON reply. Python errors are replies with `status: "error"`;
the CLI exits 1. Transport errors exit 2; their execution outcome may be unknown.
**Never automatically replay code or browser actions.**

```sh
# In one terminal:
uv run python driver.py execute 'counter.value = 7; exec("while True: pass")' --timeout 30
# In another terminal, while the kernel is busy:
uv run python driver.py interrupt
# Reset kernel memory, including saved_counter:
uv run python driver.py restart
```

Interrupt bypasses the execution lock. Restart interrupts busy Python, joins the
serialized queue, destroys the old kernel, emits `state_lost`, then boots a new
generation with a fresh counter at zero. Object IDs may be reused after restart;
identity comparisons are meaningful only **within the same generation**.

## State and execution contract

- `Counter` and `counter` exist only in the kernel. Server/browser JSON is a
  display projection, never a second authoritative counter or mutation input.
- Browser actions generate fixed, constrained Python snippets. Agent Python is
  sent through a separate `.run/agent.sock` Unix socket (directory mode 0700,
  socket mode 0600). There is **no network/browser arbitrary-execute API**.
- Commands run one at a time. Every Jupyter exchange waits for both the matching
  `execute_reply` and matching IOPub `idle`, keyed by parent request ID. The
  response reports `request_id`, `reply_received` and `idle_received`.
- Explicit `publish_state()` displays a custom JSON MIME payload containing only
  `counter.value` and `id(counter)`. The runtime deliberately executes this
  helper after each command, even after a Python exception. Call it inside a
  long-running command to publish intermediate updates. It is not magical
  observation: background-thread mutations without publication are not tracked.
- A Python exception does **not** roll back earlier mutations. For example,
  `counter.value += 3; raise ValueError("after mutation")` returns an error and
  publishes the new value. Errors in the projection clear the displayed state
  rather than calling arbitrary `repr` or pretending the old display is current.
- The fixed projection requires an exact integer within ±10^12. Arbitrary agent
  code can break/rebind `counter`, `Counter` or `publish_state`; this is a trusted
  workspace, not an enforced object-capability boundary. Restart repairs the demo
  namespace. Browser values are validated before code generation.
- Output is capped at 8192 characters per reply; error summaries at 1000. Rich
  HTML/images are not forwarded to the browser. User-requested expression results
  may invoke normal IPython repr, but state inspection itself never does.
- Queue waiting is limited to 5 seconds (rejection means code was not submitted).
  Python execution timeout is 0.1–30 seconds (default 10). On timeout the runtime
  interrupts and waits up to 3 seconds for reply+idle, then requires restart if
  unresponsive. A post-command projection has its own 3-second deadline. Interactive
  kernel stdin is disabled. Driver transport waits at most 60 seconds.
- Restart reinitializes memory; it does **not** undo files, network requests,
  spawned processes or other side effects. No code replay or state restore occurs.

## Safety boundary / limitations

The kernel is **not a sandbox**: agent Python has the current user's privileges.
Keep this on loopback and do not share the Unix socket or Jupyter connection file.
HTTP Host/Origin checks and websocket Origin checks reject cross-origin browser
access; POST requires the local Origin. These are basic prototype protections,
not multi-user authentication. Other processes running as the same user remain
trusted and can use the private socket. Jupyter's own signed channels bind to
loopback; their TCP payloads are not encrypted.

Execution timeout/output truncation are not memory, process, filesystem or CPU
quotas. Interrupt cannot reliably stop all native calls or malicious code; a failed
interrupt marks the kernel unhealthy and clears the projection. Restart/clean
shutdown only owns the kernel, not arbitrary grandchildren created by user code.
Events are bounded in-memory history, not durable audit. Slow subscribers can lose
older events. The page reconnects transport, but never replays operations.

If `.run/agent.sock` exists at startup, the server refuses to remove it: establish
that its recorded owner (`.run/server.pid`) has stopped before deleting only that
stale socket. Never start a second instance against the same run directory.
Startup errors after kernel launch shut down the owned kernel and remove any
successfully created owned socket.

## Verification

The suite can run **while the user preview stays live**: its integration server
uses a separate temporary run directory/socket and a free loopback port.

```sh
deno task check
uv run pytest -q
```

Tests use real ipykernels and a real loopback server: serialized shared identity,
Python/browser publications, partial mutation after error, busy-loop interrupt,
timeout and subsequent execution, bounded output, no interactive stdin,
request-specific reply+idle, restart generation/loss/no replay, surviving external
side effects, safe projection, independent CLI processes, Origin/Host protection,
owned server/socket/kernel shutdown, and injected post-kernel startup failures.
A separate real Chrome smoke check used
buttons, form submit and Enter, observed bidirectional updates and restart loss,
and checked a 390px viewport. Visible-browser review is owned by the coordinator.

## Layout

```text
runtime.py            Serialized Jupyter executor + explicit publication bridge
server.py             Local browser routes, websocket, private Unix agent socket
driver.py             Independent-process Python CLI and async request helper
web/                  Public page + Adaptive UI live-counter component source
scripts/build.ts      Deno/esbuild browser bundle (generated browser/ is ignored)
tests/                Real runtime and server integration checks
.run/                 Ignored, private live socket/PID/server log
```
