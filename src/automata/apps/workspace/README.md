# Workspace POC

A local-first project workspace at `/project-northstar/`. The work surface remains
visible while the selected conversation opens as a closable overlay. A clear toggle
in the bottom control bar opens and closes that overlay; sending a message never
opens it automatically. The project, selected agent, saved artifact, conversations,
and drafts share one durable local state. The artifact has no visible editor in this
revision and is not erased by conversation or agent changes.

## Build and run

From the repository root with cached dependencies and Deno:

```sh
# Choose an isolated absolute runtime; never build over a live preview implicitly.
export WORKSPACE_RUNTIME_ROOT="$PWD/.agents/var/apps/workspace-development"
python .agents/skills/automata-adaptive-ui/scripts/build.py \
  --runtime-root "$WORKSPACE_RUNTIME_ROOT"
deno task --config src/automata/apps/workspace/frontend/deno.json build
env PYTHONPATH=src uv run --offline \
  --with fastapi --with uvicorn --with shelfdb==3.0.2 --with dictify==5.0.2 \
  python -m automata.apps.workspace.server --port 8787
```

Open <http://127.0.0.1:8787/project-northstar/> and use the Conversation toggle
in the bottom bar. Rebuild web assets after source changes. The server serves only
the slug page, explicit JS/CSS routes, API, and built Adaptive UI library on loopback.
Public assets and private state/profile have separate runtime directories. The
frontend builder copies the shipped router browser modules without modifying them.
Without `WORKSPACE_RUNTIME_ROOT`, the historical build/runtime default remains
`.agents/var/apps/workspace`; do not use that default during isolated development.
Reuse an already-built, compatible `lib/adaptive-ui.js` where available; no network
fetch or dependency installation is required for the cached verification recipes.

```sh
uv run --offline --with shelfdb==3.0.2 --with dictify==5.0.2 --with pytest \
  pytest -q tests/apps/workspace/test_store.py tests/apps/workspace/test_components.py
uv run --offline --with ruff ruff check \
  src/automata/apps/workspace tests/apps/workspace
uv run --offline --with fastapi --with uvicorn --with shelfdb==3.0.2 \
  --with dictify==5.0.2 --with playwright \
  python tests/apps/workspace/browser_acceptance.py
```

The browser acceptance builds current source into a temporary runtime/DB, uses a
random loopback port and isolated headless Chrome, and reads the existing cached
Adaptive UI bundle. It never writes the visible preview's state. Its router and
agent responses are explicitly **mocks**, not evidence of a real-agent exchange.

### Explicit real-agent binding

Provision the existing message-router separately, with one page participant and a
directed grant to the authorized agent participant. Permit the exact app origin
on that router. The agent must open its own private agent endpoint in Pi; Workspace
never launches an agent. Before starting the app, set:

```sh
export WORKSPACE_PAGE_ENDPOINT=/absolute/private/endpoints/participants/workspace-page.json
export WORKSPACE_AGENT_PARTICIPANT=workspace-agent
```

Only `conversation-aster` is bound in this slice. Mira remains available for stored
history/drafts but cannot send to a real agent. The bootstrap API returns only the
page participant credential, after Host/origin/Fetch-Metadata checks; it sends
`Cache-Control: no-store`, no CORS headers, and permits only the configured loopback
WebSocket in CSP. Never put endpoint files, agent/master credentials or profiles in
`web-assets`. This is same-machine isolation, not multi-user authentication.

`tests/apps/workspace/live_acceptance.py start|submit|verify
--confirm-owned-binding` is an explicitly coordinated, three-stage acceptance
helper. Defaults target the worker-owned app on 8790 and Chrome CDP 34418;
`--url`, `--cdp` and `--evidence-root` override them for explicitly authorized
loopback resources. `start` sends one harmless text and returns; after the real agent
replies, `submit` checks rendering/draft hydration and sends one form response;
after acknowledgement, `verify` checks completion and refresh without replay.
It must not be run against an unrelated browser/agent. Real response handling and
transport delivery are separate evidence.

## UI and state boundaries

Task-local `Base` components own coherent visual boundaries: `wsp-surface`,
`wsp-conversation`, `wsp-composer`, and `wsp-controls`. They render light-DOM
content inside the `wsp-root` parent shadow root. Each component's `static css`
is registered by Adaptive UI on that containing root; there are no per-component
shadow roots or duplicated inline styles. `workspace-root.css` owns the internal
layout, while document CSS handles the page frame. `workspace-tokens.css` defines
public `--aui-*` roles and app spacing/radius values that inherit through the parent
root; browser acceptance checks computed styles after token overrides. The page
controller in `web/workspace.js` owns shared state and persistence. Adaptive UI
`Chat` is not reused because its private append-only log has no durable history
hydrate/replace or per-conversation draft API. No generic component framework is
introduced. `wsp-message` constructs ordered component descriptions through the
fixed `type:version` registry. `wsp-text` owns text validation; `wsp-form` delegates
rendering-data validation to shipped `Form.validateData`, renders `aui-form`, and
owns structured submission/draft state. Unknown or invalid components are rejected
or visibly fall back; payloads cannot supply executable HTML, JS, imports or tags.

The request contracts are:

- `workspace.message`, version 1: project/conversation/operation/message IDs plus
  `content: [{id, type: "text", version: 1, data: {text}}]`.
- `workspace.form-submit`, version 1: those correlation IDs plus `componentId`,
  `componentType: "form"`, `componentVersion: 1`, and string-valued `values`.
- Agent terminal reply: `{content: [{id, type, version: 1, data}, ...]}`, using only
  registered `text` and `form`. Form data is the exact catalog contract: optional
  title, submitLabel, and fields with name/kind/label/required plus text bounds or
  choices. Reply IDs are unique within a message. No task is executed by this demo.

Python validates bounded persistence envelopes, identities and interaction states,
not a second copy of Form's schema. The browser component registry is the rendering
contract authority; untrusted persisted content still passes it before rendering.

State lives under `.agents/var/apps/workspace/data/` as one ShelfDB value keyed by
`project-northstar`. Schema version 2 keeps only the selected artifact and conversation
in `view`; overlay open/closed state is transient and there is no route-switching
field. Writes compare and increment the revision in one transaction; stale writes
return 409. The fixed project, artifact, agent, conversation, session, and view
identities are validated. Version 1 state is deliberately not migrated; preserve any
needed old local data before switching this prototype to the new schema.

Existing v2 messages normalize additively on read: original text/history/drafts
remain intact and gain a text component plus historical-simulation provenance. A
read does not rewrite the DB; the next explicit save persists the extra fields.
The legacy conversation `sessionId` is a historical slot marker, not a live Pi
identity. Authenticated responder participant/session identity is retained with the
completed interaction. Older UI code can still show the text fallback, but cannot
render or manage forms; preserve a DB backup before any promotion or rollback.

The UI uses the shipped browser router client directly. A pending operation is
saved before transport; local persistence, forwarding/admission and agent completion
are distinct. Form submission locks immediately and remains disabled after an
acknowledgement, failure or uncertainty. Interrupted pending state becomes uncertain
on hydration; neither history loading nor reconnect replays requests. There is no
automatic retry and no UI resend of an uncertain operation. A reply timeout is
conservative uncertainty, not proof that the agent did not handle the request.
A 409 keeps local values and offers recovery copy rather than overwriting the
winner. A reply received but not saved stays in the tab with an explicit error.

The legacy POST `/api/conversations/{id}/messages` and `append_message` remain an
explicit **local simulator** for historical regression tests only. They create
`[Simulation]` replies and are not used by the current UI or real-agent flow. Their
same-operation idempotency remains tested; it is not an exactly-once guarantee for
the external router. No durable external delivery reconciliation, backup system,
multi-user authentication or multi-agent orchestration is supplied. The hidden
artifact has no editing or reveal control in this minimal layout.
