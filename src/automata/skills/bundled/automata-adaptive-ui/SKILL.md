---
name: automata-adaptive-ui
description: Use when creating or revising browser interfaces, choosing component and state ownership, or previewing and promoting UI experiments. Applies to websites, dashboards, forms and interactive tools; not general browser automation or transport setup.
---

# Automata Adaptive UI

Build an interface around what the user needs to see, decide or change. Choose the
least-complex composition that supports that interaction; a useful UI does not
require an application framework, agent connection or persistent runtime.

## Choose the surface and state

Reuse a suitable interface and verify its preview identity before creating another.
Respect an existing application's stack and maintained source. For a new standalone
interface, use the shipped library by default: reuse suitable catalog components
and extend `Base` for task-local components rather than rebuilding its foundation.
An explicit user stack choice or incompatible requirement can justify an alternative;
explain the reason. A missing build prerequisite is not itself a reason to switch.

Distinguish the work an interaction requires:

- **Static content:** render information directly; no reactive state is needed.
- **Browser-local interaction:** keep selection, input drafts and local filtering
  in the browser. Use Arrow when reactive rendering helps, not for every element.
- **External computation or state:** send explicit commands to its owner and render
  validated results. A browser snapshot is not a second authoritative dataset or
  live Python object. Use a persistent runtime only when object continuity helps.
- **Agent judgment:** request interpretation or a new action when needed; ordinary
  controls should not require an agent turn just to update their display.

These can coexist in one page. Identify the owner of each state rather than making
one framework, transport or storage mechanism mandatory for the whole interface.

## Compose around data contracts

Each component owns its input/output data contract, validation and interaction
state. The page composes components and connects data sources without redefining
those contracts or conflating independent pending actions. Logical ownership does
not require separate files or permanent catalog components.

Use JSON-compatible data at integration boundaries; parse JSON text before schema
validation. For the shipped components, direct `applyData` callers validate with
`validateData` first. Distinguish pending input, confirmed results, errors and
unknown/disconnected state. A transport receipt is not completion. Apply a reply
only to its originating, still-current component; do not replay uncertain actions.
The component need not know whether its data came from Python, an agent or a file.

Use public exports and semantic tokens rather than private library internals.
Page styles own layout/theme; component styles own internals. Preserve useful input
when updating a component: replacement, changed form fields and full reloads can
lose drafts. Consult the affected component's contract before assuming preservation.
Arrow and Shadow DOM are not security sandboxes.

## Find the implementation details

The library, builder and examples ship with this skill. Resolve these paths against
its directory and treat installed assets as read-only. Read the relevant contract,
not the entire library, before using an API:

- `lib/example/index.html` and companions: catalog composition, registration,
  page-local components and CSS-in-JS.
- `lib/example/dashboard.html`: a custom `Base` component with `validateData` and
  `applyData`, JSON-compatible sample rows, local filtering, loading/error states
  and resize cleanup. Adapt its data source rather than copying a server design.
- `lib/example/reactive-shadow.html`: optional Arrow reactivity and Shadow DOM.
- `lib/src/ui/adaptive-ui.ts`, `lib/src/ui/tokens.ts` and relevant component modules:
  exact exports, schemas, registration, styling and update semantics.
- `scripts/build.py --help`: prerequisites, build/preview commands and output layout.

Build a missing or stale library only when needed and authorized, outside installed
source. Share built assets within a website root; isolate experiments that could
disrupt another preview. Obtain approval before fetching missing dependencies or
installing runtimes. No separate UI tool or particular communication channel is
required; an external integration retains its own setup and authority boundaries.

## Revise and retain deliberately

Use temporary browser-local drafts for quick comparison; use maintained source when
reproducibility matters. Preserve useful inputs and validate a replacement before
retiring good instances. Dispose old listeners/timers and fence stale callbacks.
Custom-element registrations cannot be undone; a revision may need a distinct name.

Save draft state only when recovery is useful, in owned storage appropriate to its
lifetime. Keep it public-safe and serializable, excluding credentials, live handles
and pending actions. Cached code needs trusted provenance before evaluation; cache
presence is not permission. Verify restoration before promising it: browser storage
can be evicted, and restoring a UI restores neither runtime objects nor connections.

Promote a selected draft only with approval, capturing source, inputs, dependencies
and resource cleanup in maintained files. Verify independence from browser caches
and live injection. Reusable catalog additions need their own review, schemas and
tests; do not promote by modifying an installed skill.

## Preview and verify

Keep generated source with its established task and maintained changes in the
application. Serve a public-safe website root on loopback—not the entire task area;
exclude credentials, browser profiles and private operational state. Reuse verified
setup recipes and recheck changed prerequisites. Retain useful discovered commands
in approved owner-scoped data, separate from live server/browser handles.

Verify actual rendering and relevant interactions, including keyboard access, labels,
focus, responsive layout and draft preservation. For external state, check both the
command's observed effect and its displayed result, not merely HTTP success. Report
unverified boundaries; a demo does not establish general reliability.

Establish ownership and shutdown for preview processes. Stopping a preview does not
authorize deleting source, browser storage or evidence.

## Boundaries

This skill owns UI composition, state-boundary judgment and preview/draft lifecycle.
Browser control, task-space placement, installation, backend execution and transport
remain with their owners. The builder and component sources own mechanical APIs;
examples illustrate contracts without requiring their architecture.
