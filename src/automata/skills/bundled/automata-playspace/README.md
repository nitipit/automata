# Playspace core

An optional small runtime for **component → page → Router** experiments, not a
chat application or mandatory framework. Adaptive UI owns the shared foundation;
its independent Chat API is not used here. Router owns authentication, protocol,
correlation and capabilities. See the [starter](starter/README.md) for runnable
composition, payload examples, pairing and recovery mechanics.

## Build

```sh
python <playspace-skill>/scripts/build.py --runtime-root "$PUBLIC" --validate
```

`PUBLIC` is an approved public-safe root outside maintained/installed source.
Optional `--ui-source` and `--router-source` select copied dependencies. Existing
Python, Deno, Node >=20.19 and locked cached Adaptive UI dependencies are required;
no downloads, installs or process launch.

The builder copies inputs into a temporary workspace, builds one shared Adaptive
UI bundle, checks TS, transpiles ES modules and runs focused Node tests before
publication. It copies the starter plus existing Router client/protocol/session
modules and the client's required legacy reexport dependency. No duplicate
protocol, catalog, history, revisions or sample agent is included.

Prefer a fresh output root: builds preserve existing files and do not clean old
deployments or browser caches. TS checks retain the existing non-strict baseline.

## Public API

Import from `./lib/playspace.js`. Canonical signatures and data shapes live in
[`lib/types.ts`](lib/types.ts) and the linked implementation owners:

| API | Purpose / returned operations |
| --- | --- |
| [`createPlayspace`](lib/render.ts) | Owned root + trusted loader + event/change/error callbacks; `replace`, `update`, `snapshot`, `dispose` |
| [`evaluateTrustedDefinition`](lib/definitions.ts) | Explicitly evaluate an authorized factory with public Adaptive UI and authored CSS |
| [`validateSnapshot`](lib/state.ts) | Validate/clone versioned definitions and flat ordered instance layout |
| [`createCacheRecovery`](lib/recovery.ts) | Explicit namespace/same-origin key; `load`, `save`, `flush`, `dispose` |
| [`createPlayspaceRouter`](lib/transport.ts) | Existing client factory; explicit `connect`, `connectSession`, `disconnect`, `send`, `respond`, `isConnected`, `dispose` |
| [`ContractError` and JSON helpers](lib/contracts.ts) | Safe diagnostics and finite serializable data admission |

Definitions own props/state/event validators, a pure update reducer and a handle
factory. Handles expose an element, state snapshot and disposer. Component events
reach the page as local `{id, name, payload, isCurrent}` routing context, not a
mandatory wire envelope; the component's payload may be sent unchanged.

## Boundaries callers must preserve

**Trust:** structural snapshot validation precedes loading. The required loader
must authorize exact source **and CSS** before evaluation; cache presence is not
permission. The starter uses an exact authored-source allowlist. Identical
revisions are reused during the runtime's lifetime; recreate the runtime if its
trust policy changes. Evaluation is not a sandbox or dynamic dependency loader.

**Lifecycle:** validate all props/state before construction. Replacement stages
handles before committing; updates replace only the addressed instance. Invalid
input or failed staging retains last-good state. Cloned inputs prevent reducer
mutation from altering it. Staged/retired callbacks are inert. Factories own cleanup
before returning a handle; returned handles are disposed on failure/replacement.
Disposal errors are reported while other cleanup continues. Arbitrary source
effects and custom-element registrations cannot be undone.

**Persistence:** snapshots contain trusted source/CSS, ordered layout and component
props/state, not connections, credentials or send/reply capabilities. Authors must
still keep component data public-safe; JSON validation is not a secret detector.
Await saves, coordinate writers and preserve good entries on errors. Disposal
fences queued writes but cannot revoke an issued put. Cache is origin/profile
scoped and disposable; it is not a backup or proof of restart durability.

**Routing:** the facade passes existing Router packets/options through and only
adds lifetime/instance fencing. `send` returns `{id, accepted}`; forwarding may
settle after a reply and never proves application completion. Fence accepted
handlers with page intent and originating instance lifetime. `respond` requires
the actual inbound route ID. No reconnect/replay is automatic. The Pi starter
updates only on final `response` + `metadata.pi.type === "reply"`; rejection,
closure and unexpected receipts are not component results.

## Verification

`--validate` checks TS and focused Node tests against compiled runtime, the actual
starter orchestration and shared Adaptive UI exports. To rerun on built output:

```sh
PLAYSPACE_LIB="$PUBLIC/lib" node --test <playspace-skill>/tests/*.test.mjs
```

Fakes establish contracts and lifecycle ordering, not native rendering, auth or
cache persistence. The preview owner verifies real component roundtrip, reload,
invalid snapshot retention, unauthorized rejection, authorized pairing + separate
Connect, and no replay/stale callbacks. Acceptance mechanics belong in the starter.
