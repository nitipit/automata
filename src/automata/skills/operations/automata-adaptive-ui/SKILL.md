---
name: automata-adaptive-ui
description: Use when generating, previewing, updating, reconnecting to, or promoting a live Adaptive UI.
---

# Automata Adaptive UI

Create inspectable, task-appropriate web interfaces with the least-complex
composition that remains reproducible.

## Reuse and locate

Reuse and reconnect to a matching session before creating another. Discover its
website root from existing setup; for new roots, consult the build tool's defaults
and any applicable agent-data convention. Revalidate browser/server identities
before reuse. Keep credentials, profiles, build workspaces, and private operational
state outside the public website root.

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

- `lib/example/index.html`: static composition.
- `lib/example/reactive-shadow.html`: reactive state and Shadow DOM.
- `lib/example/chat-with-agent.html`: Chat + bridge integration; the component
  owns payload semantics, the page wires transport.
- `lib/src/ui/adaptive-ui.ts` and component modules: APIs and schemas.

Reuse available catalog components before creating new ones. Use `Base` for
component boundaries, Adapter for component styles, and Arrow for instance-local
reactive state and rendering. Register components before mounting templates; keep
static content static and document CSS limited to document concerns.

Each agent-connected component owns its outgoing payload, expected reply contract,
validation, and interaction state as a single source of truth. Page composition
connects and routes components; it does not redefine their schemas or conflate
pending states. Ownership is logical, not a requirement for separate files or
permanent catalog components. Adapt single-component examples when composing
multiple independent interactions.

Keep local interactions local. Use the separate agent-router capability
when communication is intended; transport carries complete JSON independently of
component semantics. Load only needed browser dependencies, with approval before
fetching missing assets or installing runtimes.

## Build and verify

Use `scripts/build.py --help` for build options, prerequisites, runtime layout,
preview commands, and recovery. Build a missing or stale library only when needed
and authorized; do not run internal build tasks in installed source. Share the
built library across session pages; choose a separate website root for experiments
that must not affect existing sessions.

Serve only public-safe assets on loopback. Verify the rendered UI and relevant
interactions, not just server startup or HTTP success. Preserve existing work when
updating: full reloads do not guarantee transient-state preservation. Reflect
accepted changes in session source rather than leaving browser-only probes.

## Lifecycle

Establish process ownership and cleanup before leaving a browser or server running.
Stopping activity does not authorize deleting pages, histories, or evidence.

Keep generated UI source with its session. Promote reusable components only with
user approval into maintained product source, with appropriate review, schemas,
and tests—not by patching installed copies.

## Boundaries

This skill owns UI composition and session lifecycle, not general browser control,
installation, image generation, or transport. Arrow and Shadow DOM are not security
sandboxes. The builder owns defaults and build mechanics; components own exact APIs.
