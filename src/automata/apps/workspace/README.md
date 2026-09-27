# Workspace POC

A local-first project workspace at `/project-northstar/`. The work surface remains
visible while the selected conversation opens as a closable overlay. A clear toggle
in the bottom control bar opens and closes that overlay; sending a message never
opens it automatically. One provisioned agent, Automata, is available; there is no
agent switching. Legacy conversations, drafts and the hidden artifact are preserved
in durable local state.

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
  pytest -q tests/apps/workspace/test_store.py tests/apps/workspace/test_components.py \
    tests/apps/workspace/test_identity.py tests/apps/workspace/test_lifecycle.py
# API surface tests additionally need cached fastapi/uvicorn dependencies:
uv run --offline --with fastapi --with uvicorn --with shelfdb==3.0.2 \
  --with dictify==5.0.2 --with pytest pytest -q tests/apps/workspace/test_lifecycle_api.py
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
on that router. The agent must open its own private agent endpoint in Pi; the
router never launches an agent. Workspace can optionally own one explicitly
configured Pi process through the separate local launcher below. Before starting
the app, set:

```sh
export WORKSPACE_PAGE_ENDPOINT=/absolute/private/endpoints/participants/workspace-page.json
export WORKSPACE_AGENT_PARTICIPANT=workspace-agent
export WORKSPACE_AGENT_ID=agent-automata
```

All three settings are required for the explicit assignment. The fixed approved
mapping is `conversation-aster` (legacy storage slot) -> `agent-automata` (stable
identity), display name Automata, router participant `workspace-agent`. Arbitrary
participant names and missing stable identity fail closed. The legacy stored row
`agentId: agent-a` remains a historical slot marker, not the current assignment.
Mira history/drafts remain stored but hidden, unbound and never sent. The active UI
selects the Aster storage slot; it never moves Mira data into that conversation. The bootstrap API returns only the
page participant credential, after Host/origin/Fetch-Metadata checks; it sends
`Cache-Control: no-store`, no CORS headers, and permits only the configured loopback
WebSocket in CSP. Never put endpoint files, agent/master credentials or profiles in
`web-assets`. This is same-machine isolation, not multi-user authentication.

### Connection and trust boundary

Pi joins the router using its private agent endpoint. Initial page load connects
only the browser transport, never starts Pi. Technical Connect/Disconnect/Reconnect
buttons are absent. Page transport recovers with up to six backoff attempts
(1, 2, 4, 8, 15, 15 seconds); after exhaustion a browser online event or page reload
starts a new bounded burst. No history, component descriptions, old form values or
operation requests are transmitted during connection/recovery. No request is
retried, including uncertain launch POSTs. There is no context-ready/restored/
understood state or participant takeover. Only a new explicit message or form
submission sends its own payload. Its `agentId` must match the assignment; other
conversation IDs cannot use the connection.

The UI separates router connectivity from agent Offline/Starting/Available/Failed.
An absent agent keeps a healthy router connection open. Non-overlapping status
checks sample granted-destination presence every 5 seconds while visible or 30
seconds while hidden. Available is a sampled presence claim, not idle/readiness. Runtime is unknown until
an authenticated router response provides `from.sessionId`. The UI labels it
**last authenticated response runtime**, clears it on disconnect, and updates it
if later responses come from a different runtime. This never proves context
continuity or silently changes stable agent identity. Stable assignment is
operator-provisioned; it is not authenticated by a matching display name.

The existing router targets participants, not runtime sessions. Token custody and
an exclusively authorized agent participant are trusted. A replacement session
holding that credential can receive a later page-push operation; response checks
cannot prevent that disclosure. Neither a malicious credential holder nor other
local processes bypassing browser origin restrictions are isolated by this POC.
The router binds replies to request capabilities and supplies participant/session
provenance; sessionId itself is supplied by the credential-holding Pi runtime.
No agent-facing history API or synchronization protocol is introduced. `/api/state`
remains the trusted local human browser's whole-state API, not multi-user auth.

### Optional explicit local agent lifecycle

Set `WORKSPACE_AGENT_CONFIG` to a mode-0600 operator-owned JSON file containing
exactly `agentId`, `participant`, `cwd`, `endpoint`, `executable`, `extension`,
`provider`, `model`, `thinking`, and `startupPolicy`. Paths must be existing absolute
paths; the agent endpoint must be private, loopback, kind agent and match the
configured participant. For this first app slice use `agent-automata` and
`workspace-agent`, matching the separately provisioned browser assignment. The
launcher itself is parameterized by agentId, not a hard-coded lifecycle manager.
The executable is an installed Pi CLI; extension is the installed/shipped
message-router extension. Use `openai-codex`, `gpt-6-astra`, `medium` for the approved
model configuration. Startup policy must explicitly bound what the agent may do.

Without this optional config, externally managed agents still work but there is
no Start/Resume control. With it, explicit **Start agent** creates one owned session;
**Resume agent** opens only its exact recorded saved session. Opening/reloading the
page never launches Pi. Launch requests accept only the configured agentId and
start/resume action, not paths, commands, session IDs, models or arbitrary RPC.
The loopback/same-origin boundary is not protection against other local processes.

The Python launcher owns a documented long-lived Pi RPC child and private state
under `<WORKSPACE_RUNTIME_ROOT>/agents/<agentId>/`. It uses a mutex and nonblocking
process-lifetime flock, inherited by the child. Competing requests/app processes
using that same configured runtime cannot duplicate launch. Unknown/orphan lock
ownership blocks replacement; it does not authorize adoption or PID-based killing.
Separate runtime roots are separate operator ownership domains: do not provision
two launchers for one agent. Router participant uniqueness additionally refuses
credential takeover, but is not a global process registry.

Before spawn, the launcher records the UUID/exact path and creates only a valid
version-3 Pi session header, per the documented session-file format. Pi then opens
that exact path with `--session`; get_state must confirm exact session/path/model/
effort before any startup prompt. Resume validates the owned header and every
JSONL entry; missing/corrupt/mismatched state fails closed, never selects newest,
scans global sessions or silently creates a replacement. The transcript remains
Pi-owned; there is no browser history import or session copying.

CLI startup disables discovered extensions, context files, skills and templates;
it explicitly loads only the configured message-router extension and exposes only
message_router. This bounded POC agent is not a general-purpose coding worker.
One approved startup prompt asks the agent to open its own supplied private
endpoint. Startup waits for verified open plus agent_settled (90-second bound),
not just prompt admission. Failure requires explicit action; no model-turn retry
or automatic relaunch is sent by Workspace. Provider-internal retries are Pi's
own behavior, not a new Workspace request. The page never receives agent tokens,
launch configuration, session filesystem paths or RPC access. Child stderr and
unneeded transcript events are not copied to app logs.

App shutdown closes owned RPC stdin, waits 5 seconds, then sends terminate only
after PID/process-start identity verification and waits 3 more seconds. Failure
retains the lock and reports a blocked replacement rather than claiming exit.
Sessions and lifecycle records are preserved. A crashed child becomes Failed with
an explicit Resume action. An existing external participant is shown Available,
never taken over. A still-running child whose router binding is lost is Offline;
this slice does not silently reopen the agent binding or replay its startup
prompt. An operator may stop the owning app and explicitly resume after recovery.

`tests/apps/workspace/lifecycle_live_acceptance.py
--confirm-one-owned-test-session --evidence-root /absolute/fresh/private/path`
is an opt-in, separately authorized real-model test: isolated router8792/app8790,
one fresh session then its exact saved resume, at most two startup prompts and two
harmless page requests. Never rerun a failed envelope without renewed authorization.
It retains get_state/identity, reply, screenshot and shutdown evidence, then stops
only its own app/router/browser. Fake-process tests separately cover failures,
corruption, concurrent launch, inherited/orphan locks and shutdown refusal.

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
remain intact and gain a text component plus historical-simulation provenance.
Simulated messages keep their Aster/Mira historical labels, never Automata. Earlier
real replies are displayed as Automata only where a correlated completed interaction
records `workspace-agent` and a runtime session; otherwise identity is unverified.
New replies persist explicit assigned-author provenance. Stored provenance is local
application evidence, not a cryptographic attestation. A
read does not rewrite the DB; the next explicit save persists the extra fields.
The legacy conversation `sessionId` is a historical slot marker, not a live Pi
identity. Authenticated responder participant/session identity is retained with the
completed interaction. Older UI code can still show the text fallback, but cannot
render or manage forms; preserve a DB backup before any promotion or rollback.

The UI uses the shipped browser router client directly. Local saves cannot overwrite
the separate connection status. A pending operation is
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
