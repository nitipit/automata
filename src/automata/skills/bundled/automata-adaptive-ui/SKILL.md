---
name: automata-adaptive-ui
description: Use when creating or modifying browser interfaces, websites, web-app frontends, dashboards, forms, or interactive tools; also when previewing, reconnecting to, or promoting an existing Adaptive UI.
---

# Automata Adaptive UI

Create inspectable, task-appropriate web interfaces with the least-complex
composition that remains reproducible. For a new standalone browser interface,
use the shipped library as the default composition layer: reuse suitable catalog
components and extend `Base` for task-local components. Do not read the examples
and then recreate their foundation with a separate vanilla component system.
Keep simple content static; use Arrow only where reactive behavior is useful.

Respect an established application's stack rather than replacing its framework.
An explicit user stack choice or an incompatible requirement can justify a
different implementation; explain the reason. If the library is unavailable,
check its documented build path and report the specific prerequisite rather than
silently abandoning it.

## Reuse and locate

Reuse a matching UI and reconnect to its preview before creating another. Follow
`automata-task-space` for generated UI source and task assets; reuse the established
task area rather than creating a session-specific directory. For an existing
application, keep changes in its maintained source. Discover an existing website
root from setup, or select a public-safe root within the task area—not the whole
task space. Revalidate browser/server identities before reuse. Keep credentials,
profiles, build workspaces, and private operational state outside the served root.

Consult saved recipes before rediscovery. When setup requires discovery, save verified
build/preview commands with required paths, inputs, checks and cleanup in approved
owner-scoped data, separate from live session handles. Report the location; recheck
changed prerequisites and update after verification. Do not duplicate builder help.

The library, builder, and examples ship with this skill; no separate UI tool
installation is needed. Treat installed source as read-only. Resolve the paths
below against the skill directory, not the shell's working directory.

## Compose

Inspect only relevant examples and component contracts, and adapt rather than copy
blindly:

- `lib/example/index.html` and its companion files: page composition, CSS-in-JS,
  page-local assets, and internally shared components.
- `lib/example/reactive-shadow.html`: reactive state and Shadow DOM.
- `lib/example/dashboard.html`: task-local chart with resize/disposal, Arrow
  filtering and sorting, validated sample data, and loading/empty/error states.
- `lib/src/ui/adaptive-ui.ts`, `lib/src/ui/tokens.ts`, and relevant component
  modules: public exports, semantic tokens, exact APIs and schemas.

Reuse the maintained `Base`, `Button`, `Card`, and `Form` catalog before
creating task-local components. `Base` extends Adapter (component-scoped styles,
registration and `create()`); register with `define(tagName)` before creation or
mounting templates. Edictor validates catalog data via each component's static
`validateData`; direct `applyData` callers validate first. Arrow supplies optional
local reactive state and rendering; keep static content static. Page CSS owns document
layout and theme; component CSS owns internals through `Base.css`. The index example
shows both scopes in companion `.css.js` modules; use `.css.ts` only with an existing
compilation step, not as a direct browser import.

Public `tokens` exports semantic CSS values (`surface`, `text`, `mutedText`,
`border`, `action`, `actionHover`, `actionText`, `danger`, `focus`, `status`).
Each value uses `var(--aui-<role>, fallback)`: override custom properties on
an ancestor or component; defaults remain usable without a theme service.
For example, `:root { --aui-action: #2456a6; }` changes action controls.
Do not import private `_tokens` or component token modules as public APIs.
`Form.applyData` retains text drafts by name/kind and radio selection only if
its value remains offered; removed or changed-kind fields lose drafts. Use native
`form.reset()` to explicitly clear drafts to blank defaults. Attribute changes
reconcile Button/Card/Form.

Each agent-connected component owns its outgoing payload, expected reply contract,
validation, and interaction state as a single source of truth. Page composition
connects and routes components; it does not redefine their schemas or conflate
pending states. Ownership is logical, not a requirement for separate files or
permanent catalog components. Adapt single-component examples when composing
multiple independent interactions.

Keep local interactions local. Use the separate message-router capability
when communication is intended; transport carries complete JSON independently of
component semantics. Load only needed browser dependencies, with approval before
fetching missing assets or installing runtimes.

## Build and verify

Use `scripts/build.py --help` for build options, prerequisites, runtime layout,
preview commands, and recovery. Build a missing or stale library only when needed
and authorized; do not run internal build tasks in installed source. Share the
built library across pages within a website root; choose a separate website root
for experiments that must not affect existing previews. Builder output defaults
do not determine where task-specific UI source belongs.

Serve only public-safe assets on loopback. Verify the rendered UI and relevant
interactions, including keyboard navigation, focus feedback, labels, responsive
layout, and compatible Form draft preservation—not just server startup or HTTP
success. Preserve existing work when updating: full reloads do not guarantee
transient-state preservation. For maintained interfaces, reflect accepted changes
in UI source rather than leaving browser-only probes. Explicitly temporary
browser-local experiments may retain drafts in browser storage until approved
promotion.

## Lifecycle

Establish process ownership and cleanup before leaving a browser or server running.
Stopping activity does not authorize deleting pages, histories, or evidence.

Keep generated UI source with its task. Promote reusable components only with
user approval into maintained product source, with appropriate review, schemas,
and tests—not by patching installed copies.

## Boundaries

This skill owns UI composition and preview lifecycle, not task-space placement,
general browser control, installation, image generation, or transport. Arrow and Shadow DOM are not security
sandboxes. The builder owns defaults and build mechanics; components own exact APIs.
