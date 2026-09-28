# Ongoing conversation posts

Workspace conversations are durable destinations, not request/reply threads.
An authorized agent can post acknowledgements, progress and results independently,
including while every browser is closed. This does not copy Pi history into the
browser or imply that a new Pi context knows earlier conversation history.

See [README](README.md) for app usage and boundaries and
[PROVISIONING](PROVISIONING.md) for isolated setup, promotion and recovery.

## Destination and authority

This slice supports exactly:

- Project storage identity: `project-northstar`; runtime directory slug: `northstar`.
- Conversation: `conversation-aster`, assigned to stable agent `agent-automata`.
- Optional contextual webboard: `main`. Omit it for conversation-only posts.
- Agent router participant: `workspace-agent`.
- Receiver: `workspace-app`, an app-owned backend service.

The existing router supports only page/agent kinds. The receiver therefore uses a
**dedicated private page-kind transport credential**, not a browser credential or
human identity. No Pi session is launched for the receiver. The app owns a Node
adapter using the maintained router client, with a private stdin/stdout channel to
Python persistence. The receiver credential is never an HTTP/bootstrap asset.

An explicit `workspace-agent -> workspace-app` grant is necessary. Agent authors
are derived only from router provenance: kind agent, configured participant
`workspace-agent`, and nonempty bounded sessionId. Payload-supplied author/actor
fields reject. The router authenticates credential custody; sessionId is supplied
by that authenticated runtime, not an independent cryptographic identity proof.
Other local processes with stolen credentials remain outside this POC's isolation.

Use the existing authorized agent endpoint and current Pi context. Do not discover
private endpoints by scanning live state, print credentials, borrow page/app
credentials, launch a replacement agent, or change grants implicitly. A same-repo
working directory makes app docs discoverable; it does not grant filesystem,
webboard or app-source editing authority. Resolve the authorized destination from
current task context, not whichever conversation happens to be visible.

## Post and receipt

Call `message_router` with `action: "route"`, explicit `to: "workspace-app"`, and
payload exactly:

```json
{
  "operationId": "a-new-stable-operation-id",
  "context": {
    "projectId": "project-northstar",
    "conversationId": "conversation-aster"
  },
  "content": [
    {"id": "text", "type": "text", "version": 1,
     "data": {"text": "Progress is ready to review."}}
  ]
}
```

No outer kind, thread, replyToMessageId, author, component ID or executable payload
is accepted. Optional `webboardId: "main"` belongs in context only when applicable.
Component definitions, references and interaction values belong inside content.
IDs use 1–100 ASCII letters/digits/underscore/hyphen. Content has 1–16 items and a
24 KB encoded limit, within the router's 32 KiB payload limit. Text has 1–6000
characters. Agent content types are registered `text:1` and `form:1`; form data uses
the Adaptive UI Form contract (fields, title, submitLabel), not arbitrary HTML,
JavaScript, imports or custom tags. Unknown/invalid rendering data has a visible
safe fallback; persistence bounds form JSON but does not duplicate the full Form
rendering schema. Check the component contract when composing forms.

The route tool's forwarded acknowledgment is **not** a save receipt. Consume the
terminal app response with `action: "receive", replyTo: <outgoing route id>`.
A successful response payload is:

```json
{
  "status": "saved",
  "operationId": "a-new-stable-operation-id",
  "messageId": "server-assigned-uuid",
  "seq": 42,
  "createdAt": "2026-09-28T08:00:00+00:00",
  "context": {"projectId": "project-northstar", "conversationId": "conversation-aster"}
}
```

The timestamp/sequence above are illustrative. `messageId`, conversation-local
`seq`, and UTC `createdAt` are backend-owned. Saved means message and operation
receipt committed atomically, **not** human observation, agent admission, processing
or task completion. Responses may instead say `rejected` or `uncertain`.

Idempotency is scoped by authenticated stable author + exact destination context +
operationId. Agent session changes do not create a new retry scope. A deliberate
identical retry returns the **original receipt**, including original author runtime,
message ID/order/time in the saved record. A changed payload with the same scoped
ID rejects. A new post needs a new ID; operationId does not create a conversational
thread. Do not busy-poll or automatically resend after disconnect. Reconcile or
explicitly retry the identical operation when authorized. A forwarding failure or
missing response alone cannot establish whether the save happened.

## Human input and agent admission

The human browser posts the same envelope to `POST /api/conversation-posts` with
same-origin Fetch Metadata. This route always creates a local-user message; a page
cannot assert authenticated agent identity. Before HTTP, the browser retains its
exact envelope and operationId under an operation-specific localStorage key. An
unknown save stays held across reload; no automatic HTTP or agent-delivery replay.
A known saved operation is reconciled from backend messages on the next load.
An unresolved held operation requires operator review; there is no retry/discard UI.
Browser-local retained input is not a backup and is lost if that browser storage is
cleared. Saved IDs/receipts remain in backend storage.

After receiving a saved receipt, the browser sends the agent one self-contained
input containing the envelope plus `receipt` and `postTo: "workspace-app"`. Its
explicit context is the destination; it is not action permission. No whole history
or unsent drafts are sent. Pi admission and durable saving are separate outcomes.
The UI stops waiting on authenticated Pi admission; it does not hold a task-result
promise open. The receiving agent should promptly close its exact pending inbound
request with:

```json
{"status": "accepted", "operationId": "the incoming operationId"}
```

Use `message_router action=send` with the exact inbound request id as `replyTo` for
that acknowledgement. Then post any number of independent conversation messages to
the app receiver as above, consuming each saved receipt. A terminal-only answer is
not a saved conversation post. Admission does not prove the task finished; the
message's local delivery state remains separately displayed. Interrupted pending
inputs become uncertain, never executable replay queues.

A human form submission is a saved `form-response:1` content item whose data contains
`messageId`, `componentId`, the exact source `definition`, and string-valued `values`.
These references describe the interaction, not outer context. Persistence verifies
the referenced saved form definition and atomically locks that component's submitted
values. Neither refresh nor browser state writes may unlock/reset it for replay.
The form reply appears through subsequent independent agent posts.

Webboard notifications retain their separate `workspace.webboard-event` /
`workspace.webboard-result` contract. Do not infer a conversation from a board event
or manufacture conversation posts for it. The sandbox and host-confirmation boundary
is unchanged. Current managed-agent startup instructions describe both contracts;
the managed agent still has only router tools, not filesystem tools.

## Storage, catch-up and concurrency

Schema version remains 2. Read normalization preserves project/conversation/history
identities and adds `messageId` equal to the legacy ID, a deterministic local `seq`,
and `createdAt: null` to old messages. Null means the historical timestamp is unknown.
Original text, components, drafts, provenance and revisions remain. Reads do not
rewrite the database. New posts and the `postOperations` ledger are committed in
one ShelfDB/LMDB write transaction; duplicate retries do not increment revision.
Process-local path locks avoid simultaneous environment opens; LMDB serializes
writers across processes. No general event-sourcing framework is introduced.

The browser fetches current state with a single non-overlapping loop: 1.2 seconds
while visible, 5 seconds while hidden, with a 15-second fetch bound. Page disposal
aborts the fetch and removes its timer. Saves and catch-up serialize in one queue.
Messages remain backend-owned and ordered. A three-way merge preserves composer
and form edits; keyed message/components retain DOM focus and drafts. Divergent
edits become an explicit conflict with recovery-copy UI. An append-only revision
conflict may rebase browser edits once; it never replays conversation input.

CAS alone is not sufficient: even a current-revision browser PUT cannot add, delete
or edit conversation content or the operation ledger. It may save browser-owned
drafts and local delivery/interaction evidence, without resetting submitted forms.
Local delivery fields are browser evidence, not authenticated agent authorship.
The old simulator endpoint remains explicitly simulated historical behavior, not
an authenticated posting route.

## Operational limits

`GET /api/conversation-posts` reports receiver configured/phase/participant only;
it exposes no credential, endpoint path or process RPC. Receiver recovery reconnects
transport with at most six backoff attempts per outage and never replays messages.
After exhausted recovery, operator app restart is required. App shutdown closes the
owned adapter's stdin and waits, then terminates only that child if necessary.
Agent/Pi context shutdown is a separate optional lifecycle owner.

There is no durable agent-delivery outbox, automatic task execution/replay, terminal
transcript mirroring, account/RBAC, unrestricted custom components, or history import.
The full-state polling/read response and single-value ledger grow with history;
retention/pagination are not supplied. Deleting records to reclaim space requires
separate policy/authorization because deduplication depends on retained operations.
