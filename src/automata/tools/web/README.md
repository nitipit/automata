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

Open **Sessions** to see the current conversation and other saved Pi sessions
for its exact project directory in the current session store. The picker is
unavailable while Pi is replying or stopping. Selecting a row only previews
it: the last saved exchange on the persisted branch, file recency, and recorded
model and token usage where available. History is shown as bounded plain text,
without running tools or historical UI. Pi does not persist the historical
context window with its ordinary usage records, so the picker does not estimate it.

To switch conversations, use the separate **Open session** button. First close
the selected session in any terminal or other Pi. Web Chat rejects the calling
Pi's session and uses advisory locks to prevent takeover from another Web Chat
host that supports this picker, but cannot detect all terminal, older Web Chat,
or other Pi processes.

Opening a session switches native Pi in place and replaces the transcript with
that session's active history. New messages are saved back to the same session,
not a copy. Historical interactive content is inactive, and unsent drafts are
kept separate in the current tab until it reloads. Sessions not yet saved to
disk cannot be reopened through the picker.

Browser auto-open uses the configured system browser; `--no-open-browser` disables
it. Ctrl+C/SIGTERM closes the owned host/Pi process; closing chat stops pending
agent work. Do not expose the loopback server remotely or share admission/connector
credentials.
