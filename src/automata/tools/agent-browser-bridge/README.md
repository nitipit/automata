# agent-browser-bridge

Reusable loopback browser-to-Pi generic JSON transport. The installed executable
filename is `agent_browser_bridge.py`; the tool name is `agent-browser-bridge` and
the Pi custom tool name is `agent_browser_bridge`.

## Setup, status, serve

From a project containing the installed tool:

```bash
uv run --offline --no-project --script .agents/tools/agent-browser-bridge/agent_browser_bridge.py setup
uv run --offline --no-project --script .agents/tools/agent-browser-bridge/agent_browser_bridge.py status
uv run --offline --no-project --script .agents/tools/agent-browser-bridge/agent_browser_bridge.py serve \
  --runtime-root .agents/var/skills/automata-adaptive-ui \
  --session-id chat \
  --port 8787
```

`--session-id` names the public static `/sessions/chat/` route; the Pi control
handshake separately binds the actual existing Pi session id. `setup` creates/checks
`lib/` and `sessions/` below the selected runtime root; it never starts a server,
Pi, or browser. `serve` is the only command that starts a listener. It publishes a
private endpoint record at `.agents/var/tools/agent-browser-bridge/endpoint.json`
by default and removes only its own record on shutdown.

Browser messages use `{v:1,id,kind:"message",payload}` and replies use
`{v:1,id,kind:"reply",correlationId,payload}`. `payload` may be any bounded JSON
value, including `null`; it is never projected onto transport-owned text fields.
The browser API is `sendMessage(payload)`. Payload JSON is limited to 32 KiB,
complete frames to 64 KiB, and nesting to 32 levels (root at depth zero).
Objects, arrays, strings, numbers, booleans and null are supported; an absent
payload is rejected. Numbers use JavaScript finite-number semantics; integers
outside ±(2^53−1) are rejected, and numeric formatting/negative zero are not
preserved. JSON values, not original lexical formatting or key order, are the
contract. Duplicate wire object keys, non-finite numbers, non-JSON objects,
cycles, sparse arrays and lossy extra array properties are rejected. Escaped
Unicode, including lone surrogate code units, remains JSON data. Limits apply
to compact UTF-8 serialization at each endpoint, not to static UI assets.

Pi replies use `action=send`, exact `replyTo`, and `payload`; there is no `text`
argument or `chat.*` compatibility protocol. A transport receipt is not Pi
admission: admission is confirmed only by the matching canonical Pi user-message
event. Intercepted/failed asynchronous preparation leaves admission unknown.
Reply delivery means transport emission, not proof of component handling. Do not
automatically retry uncertain sends; reconnecting does not replay them.

The server mounts only `/lib/*`, `/sessions/<session-id>/*`, `/assets/*` (the
bridge browser modules), and `/health`. The endpoint record is not public.
Create the browser page under `sessions/<session-id>/` and import
`/assets/client.js`; use `sendMessage(payload)` for generic JSON delivery.
