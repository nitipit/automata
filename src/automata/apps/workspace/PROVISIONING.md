# Workspace posting: provisioning, promotion and recovery

Operator actions below are recipes, not permission to modify a live router/runtime.
Keep private configuration, endpoint credentials, state and browser profiles outside
public assets. Never use current live state as an isolated test fixture.

## Reproducible isolated verification

From this repository, with cached Python dependencies, Deno, Node with native
WebSocket, Google Chrome, and an existing compatible public Adaptive UI bundle:

```sh
uv run --offline --with fastapi --with uvicorn --with websockets \
  --with shelfdb==3.0.2 --with dictify==5.0.2 --with pytest \
  pytest -q tests/apps/workspace

# Choose a fresh evidence path; this script refuses to overwrite it.
WORKSPACE_TEST_ROOT="$PWD/.agents/var/workspace/conversation-post/evidence/my-check" \
uv run --offline --with fastapi --with uvicorn --with websockets \
  --with shelfdb==3.0.2 --with dictify==5.0.2 --with playwright \
  python tests/apps/workspace/post_acceptance.py

uv run --offline --with ruff ruff check \
  src/automata/apps/workspace tests/apps/workspace
```

`post_acceptance.py` builds source into its own runtime, copies only the cached
public `lib/adaptive-ui.js`, binds random loopback ports, provisions synthetic
credentials, runs the actual app-owned receiver and actual router, and launches
isolated headless Chrome. It closes the whole browser before two independent posts,
restarts the app, retries an identical operation and rejects a changed payload,
then reopens Chrome and checks ordered single rendering and retained drafts.
No Pi process, model turn, existing browser profile or live router is used. It
stops its app/receiver/router/browser and retains only synthetic evidence if asked.
The older browser acceptance also covers mock-delivery forms and board isolation.

## Separate isolated setup/start recipe

This is for a **new** operator-owned sandbox, not extending a current router config.
Use an explicit absolute runtime and private configuration directory; choose two
unused loopback ports. Do not use the historical default runtime implicitly.

```sh
REPO="$PWD"
SANDBOX="$(mktemp -d /tmp/workspace-post.XXXXXX)"
chmod 700 "$SANDBOX"
read ROUTER_PORT APP_PORT < <(python - <<'PY'
import socket
with socket.socket() as router, socket.socket() as app:
    router.bind(('127.0.0.1', 0))
    app.bind(('127.0.0.1', 0))
    print(router.getsockname()[1], app.getsockname()[1])
PY
)
# Ports are no longer reserved after this probe; a bind failure requires review,
# not connecting to whichever process may have acquired one.

uv run --offline --no-project --script .agents/tools/message-router/message_router.py \
  setup --config-file "$SANDBOX/router.json" \
  --page workspace-page --page workspace-app --agent workspace-agent \
  --allow workspace-page:workspace-agent --allow workspace-agent:workspace-app

WORKSPACE_RUNTIME_ROOT="$SANDBOX/runtime" \
  deno task --config src/automata/apps/workspace/frontend/deno.json build
mkdir -p "$SANDBOX/runtime/lib"
# Copy only an authorized compatible public cached bundle; no live state/config.
cp "$REPO/.agents/var/apps/workspace/lib/adaptive-ui.js" "$SANDBOX/runtime/lib/"
```

Run these in separate owned terminals/processes (foreground commands):

```sh
uv run --offline --no-project --script .agents/tools/message-router/message_router.py \
  serve --config-file "$SANDBOX/router.json" --endpoint-dir "$SANDBOX/endpoints" \
  --port "$ROUTER_PORT" --origin "http://127.0.0.1:$APP_PORT"
```

After endpoint records exist, start the app without inherited live configuration:

```sh
env -i PATH="$PATH" HOME="$HOME" PYTHONPATH="$REPO/src" \
  WORKSPACE_RUNTIME_ROOT="$SANDBOX/runtime" WORKSPACE_PORT="$APP_PORT" \
  WORKSPACE_PAGE_ENDPOINT="$SANDBOX/endpoints/participants/workspace-page.json" \
  WORKSPACE_APP_ENDPOINT="$SANDBOX/endpoints/participants/workspace-app.json" \
  WORKSPACE_AGENT_PARTICIPANT=workspace-agent WORKSPACE_AGENT_ID=agent-automata \
  uv run --offline --with fastapi --with uvicorn \
    --with shelfdb==3.0.2 --with dictify==5.0.2 \
    python -m automata.apps.workspace.server --port "$APP_PORT"
```

Setup/serve do not launch an agent. Do not launch Pi merely to test this recipe;
the synthetic acceptance above is sufficient. A separately authorized existing
agent opens only its own endpoint. Never print/copy its token or provide the
receiver credential to an agent/browser. Stop only the owned foreground app and
router after use. App shutdown disposes its own Node receiver; durable data remain.
No board asset is provisioned automatically; board setup remains independently
approved as described in README.

## Existing-runtime promotion checklist (coordinator/operator only)

1. Establish ownership of the exact app process, runtime, router, browser and
   current coordinator participant/session. Record identities without credentials.
   Quiesce sends and settle/cancel outstanding capabilities deliberately. A router
   restart invalidates in-memory reply channels, not saved operation receipts.
2. Review source/tests and the exact config diff. Do **not** run `setup` over an
   existing config. Preserve all existing participant names, tokens, grants, origins,
   endpoint paths and coordinator session identity. Add only a fresh private
   `workspace-app` page-kind participant and the directed
   `workspace-agent -> workspace-app` grant. The app needs no outgoing grants.
   Existing browser-to-agent and board behavior remains unchanged.
3. Stop the owned app gracefully. Its receiver and optional owned RPC agent follow
   their documented shutdown; an externally managed coordinator is not owned by
   app shutdown. Never kill/adopt an unowned Pi process. With writers stopped,
   create a private consistent snapshot of the current complete runtime/data and
   the relevant config/assets. Do not copy a changing LMDB directory as a backup.
4. Review/build new assets into a separate staging runtime using the explicit
   `WORKSPACE_RUNTIME_ROOT`; inspect them before copying only public assets into
   the intended runtime. Keep project-northstar/northstar mapping, existing DB,
   legacy conversation IDs, revisions, board assets and private agent records.
   Set `WORKSPACE_APP_ENDPOINT` explicitly. Never put it in public files.
5. Apply the separately authorized router config change/restart. Endpoint records
   must remain private. The connected coordinator's transport must reconnect to its
   same participant with its same existing Pi session; do not launch a replacement,
   change credentials, import history or pretend the interrupted connection survived.
   Reconnect does not replay an uncertain operation. A deliberate identical retry
   can recover a durable saved receipt when the receiver is back.
6. Start the app with reviewed explicit environment. Check
   `/api/conversation-posts` receiver phase and the same-origin bootstrap/Host guards.
   The private receiver credential must not appear in any public route, browser
   response, process log or compiled asset. `WORKSPACE_PAGE_ENDPOINT` must not point
   to `workspace-app`; both binding and receiver configuration reject that mistake.
7. Only under separate real-exchange approval, post a bounded harmless message from
   the existing authorized coordinator, consume its saved receipt, check backend
   catch-up, and test the approved human input/acknowledgement. Do not repeat an
   uncertain send merely because a UI check failed. Browser reload discards transient
   board events and unsent in-memory edits; preserve those first.

Changing router grants requires its restart in this implementation; therefore
preserving identity/session does not mean preserving the old WebSocket connection.
No automatic migration command, credential rotation or live config rewrite ships.

## Migration and rollback constraints

Migration is additive inside schema v2: old messages retain their original fields
and IDs, gain stable messageId/sequence and `createdAt: null`; old text-only messages
also retain the prior text-component normalization. Reads do not persist migration.
The next successful post/save persists these additions. New operation receipts and
messages share one atomic ShelfDB value. The revision is retained and incremented
only for successful new state mutations, not duplicate post retries.

**Never restore a pre-promotion full DB over newer backend-appended messages.**
The older backend does not enforce the new message ownership/ledger invariants and
is not a safe writable rollback target. An old frontend may be rejected by the new
backend instead of overwriting content; do not bypass that guard to make it work.

Safe rollback is operational containment: stop the affected app/receiver, retain
its current complete data directory and private configuration, and keep agents from
sending into an uncertain deployment. Preserve a new consistent post-failure copy
with all committed messages/receipts before any repair. Use a forward fix or a
verified post-aware backend with compatible assets. Do not restart old writable
code against the current DB. Restoring old assets/config alone must not delete
new data or revoke the recorded coordinator identity. An unavailable receiver is
preferable to silent history/operation loss; retries wait for explicit recovery.

If a full-state snapshot restore is necessary after corruption, that is separate
operator-authorized disaster recovery with reconciliation of every newer message
and receipt, not a routine source rollback. Keep both current and snapshot copies;
this slice supplies no automatic replay/reconciliation tool or deletion policy.
