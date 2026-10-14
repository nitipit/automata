# Optional browser counter adapter

This example embeds the **separately installed generic Python runtime tool**.
Counter/schema/publication logic is here, not in the runtime. The browser and
independent tool CLI calls work with one authoritative object in one kernel.

## Copy, build, run

Installed skill assets are read-only. Copy this example to an approved task area,
not into another installed skill directory. Requires uv, Deno, installed
`python-runtime` tool and Adaptive UI skill. No global packages are needed.

```sh
# Resolve these installed paths absolutely; there are no repository fallbacks.
export AUTOMATA_PYTHON_RUNTIME_TOOL=/absolute/.agents/tools/python-runtime
ADAPTIVE_UI=/absolute/.agents/skills/automata-adaptive-ui
WORK=/absolute/task-area/browser-counter
cp -R /absolute/.agents/skills/automata-python-workspace/examples/browser-counter "$WORK"
cd "$WORK"
uv sync --locked
python "$ADAPTIVE_UI/scripts/build.py" --runtime-root "$WORK/browser"
deno install --allow-scripts=npm:esbuild
deno task build
deno task check
uv run uvicorn server:app --host 127.0.0.1 --port 8021
```

Open http://127.0.0.1:8021/ in the intended isolated visible browser. Change port
by setting `WORKSPACE_PORT` to the same value as Uvicorn `--port`. Use a distinct
`WORKSPACE_RUN_DIR` for another instance (default `$WORK/.run`); its absolute
`agent.sock` path must be shorter than 108 bytes. Choose a shorter private run
directory when the task-area path is long. Build only in the
relocated task area; generated bundle, environment, and private socket/PID stay
outside installed assets. Only the page and `/assets/` are served, never source,
run directory, tool code or task-area files.

## Same object from an independent process

In another terminal, from the relocated example directory:

```sh
CLI="$AUTOMATA_PYTHON_RUNTIME_TOOL/python_runtime.py"
uv run --script "$CLI" execute 'saved = counter; counter.value += 10' --workspace "$PWD/.run"
uv run --script "$CLI" execute 'assert saved is counter; print(id(counter)); counter.value += 1' --workspace "$PWD/.run"
uv run --script "$CLI" status --workspace "$PWD/.run"
```

Watch the browser update with source `python`; click a browser button, then run
`execute 'print(counter.value)'` through that same CLI. This requires the explicit
tool/workspace interface: ordinary unrelated shell Python is a different process.

`publish_state()` is a fixed primitive-only display projection. This adapter
explicitly configures the runtime's `bootstrap` and `after_execute` hooks; the
latter publishes even after a Python error. For example,
`counter.value += 3; raise ValueError("after mutation")` returns an error and the
new count: no rollback. Call `publish_state()` inside long-running Python to
publish intermediate updates. Arbitrary background mutations are not observed.
The server/browser JSON is only a display cache, never mutation authority.

## Lifecycle and limits

Use the installed CLI `interrupt`, `restart`, or `stop`, always with this exact
`--workspace`. Stop or Ctrl+C gracefully shuts down the owned server/kernel and
removes its socket/PID. Verify process disappearance; do not blindly signal stale
recorded PIDs. A leftover `owner.lock` is a harmless flock handle file, not a live
owner. A leftover socket is not automatically removed: establish owner inactivity
before scoped stale cleanup.

Restart runs the **explicitly configured example bootstrap** again, creates a
fresh counter at zero and increments generation. It does not replay prior user
commands or restore data. Runtime ID changes when the entire server is replaced;
object identity is meaningful only within the same runtime ID and generation.
Restart loses all kernel memory, not external filesystem/network/process effects.

Kernel is **not a sandbox**. Agent code and same-user local processes are trusted
and can replace the example namespace/publication helper. Browser actions are
constrained/validated snippets; there is no network execute endpoint. Local
Host/Origin and websocket Origin checks are basic browser protection, not multi-user
authentication. Private Unix transport is user-only; Jupyter's own signed channels
bind loopback but their payloads are not encrypted.

Counter projection requires an exact integer within ±10^12; it never calls an
arbitrary object's repr. Invalid projections clear the display. User-requested
Python expression output can still invoke normal IPython repr. Output and timeouts
are bounded, not resource quotas or reliable sandbox limits. Native/malicious code
may resist interrupt; unhealthy kernels require restart. Shutdown does not own
arbitrary subprocesses created by agent code. Events are bounded/nondurable.
Transport reconnect never replays an action.

## Files

- `server.py`: loopback browser routes and explicit installed-tool embedding.
- `counter.py`: Counter bootstrap, state schema and publication adapter.
- `runtime_import.py`: required installed-tool location (no source fallback).
- `web/`: Adaptive UI component and page; minimal public TypeScript declarations.
- `scripts/build.ts`: bundles only this example; imports built Adaptive UI assets.

Reusable runtime and client implementation exists only in the installed tool.
Repository integration tests install both assets into temporary roots, copy this
example elsewhere, exercise it against the installed tool, and clean their own
server/socket without touching an already-running user preview.
