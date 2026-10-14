---
name: automata-adaptive-ui
description: Use for composing browser interfaces, choosing component/state ownership and previewing or promoting UI drafts. Not for browser control or transport setup.
---

# Automata Adaptive UI

Choose the simplest interface for what users need to see, decide or change. A UI
needs neither an application framework nor an agent connection by default.

1. **Choose surface and state.** Reuse suitable interfaces and verify preview identity.
   Respect existing stacks; for new standalone work default to the shipped catalog
   and task-local `Base` extensions. User choice or incompatibility can justify an
   alternative, not a missing prerequisite alone. Render static content directly;
   keep drafts/filtering in the browser and use Arrow only where reactivity helps.
   External computation/state needs explicit owner commands and validated results,
   not a second authoritative browser snapshot. Persistent runtimes serve object
   continuity; ordinary controls need no agent turn. Different state owners may coexist.

2. **Compose through contracts.** Components own data contracts, validation and local
   interaction state; pages compose them without redefining contracts or mixing pending
   actions. Logical ownership need not imply separate files/catalog components.
   Use JSON-compatible boundary data; parse text before actual-data validation.
   Primitives use typed/native properties, not required appearance schemas; custom
   components may use `Base.validateData` for meaningful data. Distinguish pending,
   confirmed, error and disconnected states; receipts are not completion. Apply replies
   only to originating current components and never replay uncertain actions.
   Use public exports; page CSS owns layout, component CSS owns internals. Preserve
   useful drafts and inspect contracts before replacement. Arrow/Shadow DOM are not sandboxes.

3. **Read relevant implementation details.** Installed assets remain read-only:
   - `../automata-web-app/examples/webapp/README.md`: runnable design pages and usages.
     Without the sibling, library contracts still work; app integration needs a source.
   - `lib/src/ui/adaptive-ui.ts`, `lib/src/ui/tokens.ts` and relevant modules: public
     exports, primitive values, native behavior. Catalog: Button, Card, native Form, Base.
   - `scripts/build.py --help`: build/preview prerequisites and output layout.
   Build missing/stale assets only when needed and authorized, outside installed source.
   Share builds within website roots; isolate disruptive experiments. Missing dependencies
   or runtimes need approval, not silent fetching or a different mandatory transport.

4. **Revise and promote deliberately.** Browser-local drafts suit comparison;
   maintained source suits reproducibility. Preserve inputs and validate replacements;
   dispose listeners/timers and fence stale callbacks. Custom-element registration
   cannot be undone, so revisions may need new names. Save public-safe serializable
   draft state only within useful recovery authority, never credentials, live handles
   or pending actions. Cached code needs trusted provenance; restoring UI restores
   neither runtime objects nor connections and browser storage may be evicted.
   Promotion/catalog additions need explicit scope and maintained source/dependencies/
   cleanup; verify independence from injection/caches. CSS owns appearance, not schemas
   or aesthetic assertion tests. Never promote by editing installed skills.

5. **Preview and check useful behavior.** Serve only a public-safe loopback website
   root, excluding private operational state and profiles. Reuse setup, recheck affected
   prerequisites and save useful discoveries only in approved owner storage, not live
   handles. Check rendering, relevant interaction, keyboard/labels/focus, responsive
   layout and draft preservation. External operations need observed effect and displayed
   result, not HTTP success. Report limits; own preview shutdown, with no implied
   source/storage/evidence deletion.

This skill owns UI composition and draft/preview judgment. Builders/components own
mechanical APIs; examples illustrate, not mandate, architecture. Placement, browser
control, installation, backends and transport remain with their owners.
