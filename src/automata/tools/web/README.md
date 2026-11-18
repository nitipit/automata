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

One `automata web` invocation serves the project's chats on one loopback HTTP
port. Each chat has its own native Pi process and URL at `/sessions/{native-id}/`.
**New chat** opens a separate tab on the same port with a fresh native session;
it does not interrupt or move the original chat. Both can answer at once, and
**Stop** affects only the current session.

The private admission URL is not printed. Its scoped credential is stored by
native session ID in that tab's `sessionStorage` and removed from the address.
A clean URL alone is not admission. A second writer for an attached session is
refused; it does not evict the original tab. Refresh reconnects to the same host
and Pi while that session is retained. Retry connection is available after
transport failures. Missing or rejected credentials require a valid admission URL
and never start a new agent. If tab storage is unavailable, reopen the original
admission URL after a refresh, while the host still owns that session.

Disconnecting or refreshing interrupts only that chat's pending reply rather
than continuing background generation. Reconnection restores its transcript,
including any retained partial reply; it never resends prompts or replays
historical UI code.
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

To open a saved conversation, use **Open session** after closing it in any
terminal or other Pi. Web Chat rejects the calling Pi's session and uses
advisory locks to prevent concurrent writers among cooperating Web Chat hosts.
It cannot detect all terminal, older Web Chat, or other Pi processes.

On success, the current tab navigates to the saved native session; the original
Pi is not rebound. A refusal leaves the current tab and draft intact. New
messages are saved back to the selected session, not a copy. Historical
interactive content is inactive. Drafts are kept separate for intentional picker
navigation in that tab, not persisted through ordinary reload. Sessions not yet
saved to disk cannot be reopened through the picker.

A host owns at most four native sessions at a time, including ones starting or
closing. A browser has 10 seconds to attach both transports. Detached sessions
are retained for 120 seconds after cleanup for refresh; unused new chats are
retired if they do not attach within 120 seconds. Closing one chat stops only
its pending work. If all chats have expired, restart `automata web` to get a new
trusted admission URL. These limits do not apply to ordinary terminal Pi.

Browser auto-open uses the configured system browser; `--no-open-browser` disables
it. Ctrl+C/SIGTERM closes all owned Pi processes and the shared listener. Do not
expose the loopback server remotely or share admission/connector credentials.
Same-origin generated JavaScript is trusted, not isolated by a security sandbox.

Maintainers: the pinned Web Runtime is single-browser. The shared-listener
adapter embeds one unstarted child ASGI app per admitted pair by attaching it to
the parent's origin and running state. Upgrade the runtime only after validating
this compatibility seam with real bridge and browser tests.
