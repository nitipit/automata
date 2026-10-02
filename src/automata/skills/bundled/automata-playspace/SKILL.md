---
name: automata-playspace
description: Use when exploring ideas together in a temporary browser playspace, creating or revising live UI drafts with Playwright, restoring browser-cached experiments, or explicitly promoting a selected draft. Not for ordinary maintained UI development.
---

# Automata Playspace

Use a temporary browser surface to think, compare and revise with the user.
Keep recoverable experimental definitions and state in browser Cache Storage;
do not make every draft a maintained source file or build a chat application.
Ordinary maintained interfaces should remain reproducible in project source.

## Choose the surface

Reuse a suitable playspace and working browser connection before creating another.
Follow Adaptive UI's composition guidance and public components rather than
recreating its foundation. Browser connection, profile selection and process
control retain their existing owners.

Serve only public-safe assets on an authorized loopback origin, separate from
credentials, profiles and private task records. Dependencies and asset fetching
require their own authority; this skill does not grant installation permission.

Choose the shell and component composition for the experiment. There is no
required board, registry or global payload envelope. The optional runtime in
`lib/` provides a small component lifecycle, Cache I/O and thin Router facade;
its flat snapshot format is not mandatory for other experiments.

See [README.md](README.md) for public API/build boundaries and
[starter/README.md](starter/README.md) for runnable examples and mechanics.
The starter teaches one component → page → Router, not history, revisions or a
sample agent. Adaptive UI's independent Chat API is not used by this core.

## Revise deliberately

Author and mount trusted component/CSS drafts through the established browser
connection. They may remain JavaScript and browser-local until promotion.
Preserve unrelated drafts and compatible interaction state when revising.

Validate replacements before discarding good instances where possible. Reuse a
known definition or use a distinct custom-element registration for a revision;
registrations cannot be undone. Release replaced listeners, timers and handles,
and fence stale component callbacks from changing the current draft.

Only execute definitions whose trusted agent-authored provenance is established.
Authorize exact source **and CSS** before factory evaluation. Structural validity,
cache presence and cached trust flags are not execution permission. The starter
admits only its exact authored definition/CSS; live revisions need an explicit
owner-approved loader change. Evaluation is not a sandbox, and arbitrary source
effects cannot be rolled back.

## Connect only useful interactions

Keep local interactions local. Each connected component owns its request/reply
JSON, validators and independent interaction state. Page composition selects the
destination and uses the existing Message Router client; do not duplicate its
authentication, protocol or capability machinery.

Apply only validated successful replies to their originating component. Display
rejection, invalid replies and uncertain delivery without destroying good results.
Forwarding is not completion, and a terminal rejection is not a successful reply.
Fence response callbacks and awaited completion handlers against both retired
page intents and replaced component instances.

Router connection is optional; authentication is mandatory when used. An
authorized agent may privately provision a pairing code and redeem it through
the existing page auth client. The page gains no approval authority. Pairing,
explicit Connect, Disconnect and operator-owned revocation remain distinct.

Restoration reconstructs drafts, not connections. Revalidate an authorized
connection before enabling sends; never auto-connect, reconnect or replay work.
A surviving pairing cookie is not a native agent binding or delivery permission.
Restore pending display as interrupted/uncertain, never as a queued send.

## Persist and recover

Use Cache Storage directly; no service worker or IndexedDB is required. Choose
an owned namespace and same-origin key, preserving other experiments' entries.
Save trusted source/CSS, layout and serializable component inputs/state needed
for reconstruction, not DOM nodes, closures or live handles.

Keep credentials, pending sends, connections and reply capabilities out of
snapshots. Component authors must keep source/props/state public-safe too:
JSON validation is not a secret detector. Await writes before claiming a version
is saved; subsequent edits may still be unsaved. Coordinate writers where needed;
Cache API is not a transactional shared-state service.

Make unavailable storage, malformed snapshots and failed reconstruction visible.
Retain the last-good draft and cache on failure; do not silently erase or repair
records. Preserve origin/profile, cache location and shell prerequisites in task
context when continuation needs them. Cache is disposable, not a backup; reload
recovery does not prove restart recovery, and eviction may lose drafts.

## Verify, promote and retire

Verify visible interactions, keyboard access and relevant layout. Check actual
definition/state recovery on refresh, and replacement/disposal or cache failures
when those behaviors matter. Test the same profile/origin across restart before
promising restart recovery. Report unverified boundaries without expanding scope.

Promote only the explicitly approved component/CSS and destination. Export its
source, required data/styles/dependencies and resource lifecycle into maintained
source, then verify independence from draft cache and live injection. Liking a
visual is not promotion permission; do not patch installed skills automatically.

Clear only exact owned entries within cleanup authority, preserving useful drafts
first. Finishing a discussion or stopping a preview does not authorize deleting
browser data, evidence or files. This skill owns experimental draft lifecycle,
not general UI composition, browser control, transport or installation.
