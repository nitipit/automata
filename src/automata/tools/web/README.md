# Browser-first Pi host

`automata web` starts a **fresh** Pi RPC session and one loopback server on the
existing `automata_web_runtime.WebRuntime.app`. It does not migrate a running Pi,
require a Python kernel, or use NodalWire. Pi must already be installed/configured.

## Build and run

From the Automata source checkout (Python >=3.12 and Node/npm for source builds):

```sh
npm ci --ignore-scripts
npm run build:web
uv sync --extra web
uv run automata web --provider openai --model <configured-model> --thinking medium
```

The `web` extra pins the reviewed upstream runtime commit. Building that dependency
from source also requires Node/npm; its wheel includes its browser assets.
`npm run build:web` builds the application entry using the real official JSR
Adapter 4.0.0, not the stale similarly named npm package. Application wheel/sdist
builds use the packaged `public/index.js`; run the frontend build **before**
`uv build`. Installed application wheels need no Node/npm at runtime.

The root command is a thin call to the host, not a second web CLI/server. Options
include `--cwd`, `--pi`, `--port`, `--provider`, `--model`, `--thinking` and
`--no-open-browser`. Omitted model settings use Pi's configured selection; no
fallback/substitution is performed. Browser auto-open uses the user's configured
system browser. For controlled agent trials, open `host.runtime.url` privately in
an approved isolated browser instead (the async `BrowserHost` API permits this).
`--no-open-browser` suppresses auto-open; the token-bearing URL is deliberately
not printed. Shutdown is Ctrl+C/SIGTERM.

## Trust and lifecycle

This is trusted-local, single-browser operation. The browser admission token lives
in a fragment until upstream `/bridge.js` consumes it; the application then erases
it. A separate environment-only bearer credential connects the Pi extension to
HTTP connector routes. Neither secret should be logged, copied to shared messages,
or included in screenshots. Exact loopback Host/Origin and bearer checks are not
remote-access support. No repository/task-directory static mounts exist.

Agent JavaScript executes with full page privileges. The generated UI area is a
layout convention, **not a sandbox**. A JS timeout/cancel/disconnect does not undo
browser effects; inspect before repeating. Event subscriptions are correlated,
bounded and tied to the exact browser session, never silently retargeted.

Chat displays streamed text and authoritative final messages. Only native
`agent_settled`, not `agent_end`, denotes idle. Native confirm/select/input/editor
requests are supported with fail-closed cancellation and a maximum host deadline
of 120 seconds. Stop cancels connector waits/dialogs, clears Pi's pending queue
**before** abort, and has a 10-second overall deadline. Further native dialogs
requested by a sequential command during Stop are automatically cancelled, allowing
its original prompt to release the command lock; this does not preempt arbitrary
non-cooperative extension code. An unconfirmed Stop retires
the owned Pi process through bounded EOF/TERM/KILL cleanup and reports an error;
restart the application rather than blindly retrying. Closing a browser stops
owned model work; reconnecting does not replay page-local generated UI.

## Checks and evidence boundaries

Host unit tests are `tests/unit/automata/tools/web_test.py`. The opt-in
`tests/integration/automata/tools/web_smoke.py` requires prepared web/Playwright and
an existing Chrome executable. It checks actual built assets, host, fresh Pi,
upstream bridge, native RPC dialogs and correlated **automated synthetic** input
without any provider call. This does not prove a conversational model trial or
actual human participation. Model-backed and human-input acceptance must be
coordinated separately with an explicit model, budget and participant.
