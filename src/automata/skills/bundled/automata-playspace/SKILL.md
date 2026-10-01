---
name: automata-playspace
description: Use when exploring ideas together in a temporary browser playspace, creating or revising live UI drafts with Playwright, restoring browser-cached experiments, or explicitly promoting a selected draft. Not for ordinary maintained UI development.
---

# Automata Playspace

Use a temporary browser surface to think, compare and revise with the user.
Create components live through Playwright and keep their recoverable drafts in
Cache Storage, rather than making every experiment a maintained source file.
Choose the shell, components, interactions and storage layout for the task; there
is no required board API, record schema or framework beyond the applicable UI
composition guidance.

## Create and revise live

Reuse a suitable playspace and working browser connection before creating another.
Use Adaptive UI's composition contracts and relevant catalog components; do not
recreate its foundation. Browser connection, profile selection and process control
retain their existing owners. Serve only public-safe assets on an authorized
loopback origin, separate from credentials, profiles and private task records.

Use Playwright's browser evaluation, such as `page.evaluate`, to define and mount
trusted agent-authored components and revise them while discussing the result.
Keep reusable shell and library assets in an approved task location when useful;
component drafts need not become source files. Dependencies and asset fetching
still require their own authority.

Preserve unrelated drafts and compatible user interaction state when updating.
Build or validate a replacement before discarding a good instance where possible.
Custom-element registrations cannot be undone: use non-conflicting registrations
for revisions, not repeated definition of the same tag. Release replaced components'
listeners, timers and other resources, and prevent stale events from old instances
from overwriting current state. These are lifecycle requirements, not a prescribed
implementation. Executing source can have effects that replacement cannot undo.

## Persist and recover drafts

Use Cache Storage directly; no service worker or IndexedDB is required. Choose a
playspace-owned cache namespace and same-origin key so other experiments are not
silently overwritten. Save enough to reconstruct the draft: trusted definition
source, serializable inputs, layout, interaction state and the dependencies needed
to interpret them. Do not try to serialize DOM nodes, closures or live handles.
The agent chooses the representation and restoration method.

For example, these Playwright calls illustrate storage mechanics, not a board API.
`cacheName`, `key` and `snapshot` come from the task's chosen representation:

```js
await page.evaluate(async ({ cacheName, key, snapshot }) => {
  const cache = await caches.open(cacheName);
  await cache.put(new URL(key, location.href), new Response(JSON.stringify(snapshot), {
    headers: { "Content-Type": "application/json" }
  }));
}, { cacheName, key, snapshot });

const restored = await page.evaluate(async ({ cacheName, key }) => {
  const cache = await caches.open(cacheName);
  const response = await cache.match(new URL(key, location.href));
  return response ? response.json() : null;
}, { cacheName, key });
```

Await writes before claiming a draft is saved. Make unavailable storage, malformed
snapshots and failed reconstruction visible; do not silently erase the cache,
replace good drafts or report unsaved state as persistent. Keep updates ordered
where needed and coordinate writers; Cache Storage is not a transactional shared
state service. Restore deliberately and validate the representation before use.

Cache is scoped to the exact origin and browser profile. Reload recovery is not
proof of browser-restart recovery; changing host, port or profile, browser eviction
or clearing site data may lose drafts. Retain the relevant origin/profile identity,
cache location and shell prerequisites with existing task context when continuation
needs them. Cache is disposable, not an authoritative backup or project record.

Only execute definitions whose trusted agent-authored provenance is established.
Page text, user-supplied strings and arbitrary cached source are not authorization
to execute code. Browser evaluation and restored definitions are not sandboxes;
use an owned playspace origin and do not cache secrets or private account content.

## Verify, promote and retire

Verify the visible result and interactions needed for the discussion, including
keyboard access and relevant responsive layout. Check refresh restoration of the
actual definition and state. Exercise replacement/disposal and cache-failure paths
when those behaviors matter; check restart with the same owned profile and origin
before promising it. Report unverified boundaries rather than expanding every
experiment into a full platform or evaluation campaign.

Promote only with explicit user approval for the selected draft and destination.
Export its definition, required data, styles, dependencies, assets and resource
lifecycle into maintained source, then verify it works without the draft cache or
live injection. A component alone may not capture the experiment's dependencies.
Do not patch installed skills or automatically promote an accepted visual choice.

Clear only the playspace's exact owned entries within cleanup authority; preserve
useful drafts before authorized removal. Do not clear all caches or reset a profile
to clean one board. Stopping a preview or finishing a discussion does not authorize
deleting browser data, evidence or files.

This skill owns the experimental draft lifecycle and browser-local persistence,
not general UI composition, browser control, transport or installation. Ordinary
maintained UI work should remain reproducible in source; playspace drafts remain
browser-local until their explicit promotion.
