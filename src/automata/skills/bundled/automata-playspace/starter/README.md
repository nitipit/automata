# One-component starter

This is runnable page composition, not a standalone chat app. One `Base` component
owns an editable draft, outgoing `{text: string}`, reply `{text: string}` and
serializable `{draft, result}`. Page composition sends the request to a selected
Pi participant and applies only the validated reply to that originating instance.
Text is rendered literally, never as HTML. Local editing needs no Router.

## Build and open

```sh
python <playspace-skill>/scripts/build.py --runtime-root "$PUBLIC" --validate
```

Use the approved preview/server workflow to serve only `PUBLIC` on loopback.
No server is started by the builder. Use an isolated `http://127.0.0.1:<port>`
origin; do not replace another task's live origin or serve private task files.
Existing cached dependencies only; see the parent [README](../README.md).

For local editing, a static server is sufficient. For pairing, the existing Router
must serve these public assets and same-origin `/session/*` endpoints. A plain
static preview reports auth unavailable; it does not fall back to public tokens.
Router service setup, native agent binding and browser control retain their
existing owners. See the Message Router skill/operator documentation for those
operations; this starter does not install, start or approve them.

Files have distinct owners:

- `component.js`: self-contained trusted factory/source/CSS and initial draft.
- `page.js`: component → Router routing, Pi receipt display and lifecycle intents.
- `index.js`: shared imports, Cache namespace, bootstrap and pagehide cleanup.
- `index.html` / `style.css`: small page shell and controls.

The browser receives compiled `lib/` and Router browser modules, not source TS,
tests, credentials or operator files. No catalog or examples/chat archive.

## Local editing and recovery

1. Edit the component's draft. Nothing is sent automatically.
2. **Save draft** awaits Cache API persistence. A later edit remains unsaved.
3. **Restore draft** first disconnects/invalidate pending intents, then reads,
   validates and reconstructs the saved component, CSS, layout and state.
4. Reload at the same origin/profile. Startup restores only the draft; connection
   stays disconnected, with no auth request, socket or send replay.

Cache name is `automata-playspace-core-v1`; key is the same-origin
`./__playspace_core_snapshot_v1__` relative to the page. Old chat caches are neither
read nor removed. Invalid snapshots, altered source/CSS and reconstruction failures
retain the current draft and do not erase the cache. The exact authored component
source/CSS is the starter's allowlist; arbitrary cached source is not executable
permission. Live trusted revisions require deliberately changing that loader.

Only draft/result state is saved. Pending requests, destination input, pairing
code, credentials and Router capabilities are not. Do not put secrets in the
component itself: JSON validation cannot identify private data. Origin/profile
changes, eviction and clearing site data may lose cache; this is not a backup.

## Optional authorized agent connection

1. An authorized operator/agent privately provisions the intended page participant
   and its allowed Pi destination using the existing Router operator path.
2. Redeem the operator's one-use code with **Pair**. Code redemption does not
   connect or send; approval authority never enters public assets.
3. Enter the exact authorized Pi participant ID and press **Connect**. This checks
   current session status and opens Router's authenticated same-origin connection.
4. Press the component's **Send to connected agent**. The page sends its JSON
   unchanged. The agent replies on the exact pending route with `{text: "…"}`.
5. A valid terminal Pi reply updates the component visibly. Save to persist it.

An authorized agent may redeem the provisioned code through
`await window.playspace.pair(code)` rather than making the user manually type it.
This uses the same redemption endpoint, not an approval endpoint. Keep operator
credentials/code delivery in the approved private workflow; do not cache them or
put them in URLs/source. Pairing and Connect remain separate explicit operations.
Disconnect closes the socket but does not revoke a paired cookie; revocation is
owned by the existing Router controls/operator workflow, not by this starter.

Forwarded is not admitted/completed. Pi admission is shown as waiting; only
`type: "response"`, `final: true`, `metadata.pi.type: "reply"` permits an update.
Rejection, unexpected receipt or route closure reports failure/uncertainty without
changing the last-good result. Invalid reply JSON likewise retains the result.
There is no generic peer response mode, streaming or sample-agent fallback.

Restore, Disconnect, disposal, target edits and newer Connect actions fence older
operations before auth/cache awaits. Replaced instances fence their old replies.
A late forwarding receipt cannot regress a completed/failed result to pending.
No retry, reconnection or replay is automatic, including after service restart.

## Inspection and acceptance

`window.playspace` exposes `runtime`, `router`, `save()`, `restore()`, `pair(code)`,
`connect()`, `disconnect()`, `status()`, `dispose()` and startup `ready`. The runtime
provides `snapshot()`, `replace(snapshot)` and `update(id, payload)` for trusted
page-owner inspection. These APIs are not authorization to execute arbitrary code
or operate another page. Router connection objects/credentials are not cached.

Focused Node checks exercise the actual `page.js`, authored `Base` component,
real Router callback shape, delayed auth/restore/connection/accepted completions,
trust rejection and repeated restoration. They do not establish native rendering.
The preview owner checks keyboard/focus/layout, visible reply, exact-origin Cache
reload, malformed snapshot retention, unauthorized rejection and explicit paired
connection in an isolated real browser/Router. Do not claim browser-restart
recovery without checking that boundary.
