# Pi browser chat

`automata web` is a trusted-local chat interface to a normal native Pi session,
with its usual working directory, configuration, tools and persistence. Generated
HTML/Web Components/JavaScript belong inline in assistant messages, not a separate
panel. Full-page JavaScript is **not sandboxed**. Restored UI history is inactive;
historical JavaScript is never automatically replayed. See the
[Web UI skill](../../skills/automata-web-ui/SKILL.md) for shared-component authoring
and a practical example; the Pi extension's tool definitions own exact contracts.

## Build and run

Pi must already be installed/configured. Source builds need Python >=3.12 and
Node/npm; installed wheels contain the built browser assets (Pi still needs Node).

```sh
npm ci --ignore-scripts
npm run build:web
uv sync --extra web
uv run automata web
```

Omitted provider/model/thinking options leave selection to native Pi. `--cwd`
selects the launch directory; caller environment, including intentional project
virtualenvs, is preserved. Launch a dedicated host venv's absolute Python or
executable without activating it when that venv is not the intended agent env.

To resume, first stop every other owner of that session, then select its exact
existing file explicitly (there is no automatic activity detector or takeover):

```sh
uv run automata web --session /path/to/session.jsonl --session-inactive
```

The browser admission URL is private and is not printed. Its credential is kept
in same-origin, per-tab `sessionStorage` and removed from the visible URL. Refresh
and bounded connection retries reconnect to the same existing host/Pi session;
Retry connection is available after transport failures. Missing or rejected
credentials require a valid admission URL and never start a new agent. If tab
storage is unavailable, reopen the original admission URL after a refresh.

Disconnecting or refreshing interrupts pending replies rather than continuing
background generation. Reconnection restores native history, including partial
interrupted replies; it never resends prompts or replays historical UI code.
The heading and browser tab use the saved Pi session name, then a compact preview
of the first native user message, then `Untitled session`. The adjacent edit
control renames the native session, without generating a model prompt.

Browser auto-open uses the configured system browser; `--no-open-browser` disables
it. Ctrl+C/SIGTERM closes the owned host/Pi process; closing chat stops pending
agent work. Do not expose the loopback server remotely or share admission/connector
credentials.
