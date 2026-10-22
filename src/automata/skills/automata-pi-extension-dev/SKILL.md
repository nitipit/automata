---
name: automata-pi-extension-dev
description: Use for creating, reviewing or modifying Pi extensions and their agent-facing guidance. Not for merely using an installed extension or general skill authoring.
---

# Pi Extension Development

Build against the installed Pi runtime, not remembered SDK behavior. Read its
`docs/extensions.md` and the smallest relevant extension example; follow related
API/type declarations and topic docs as needed. Do not reproduce the SDK manual.

1. **Separate discovery from reference.** Pi executes extension code but does not
   automatically put its README, source or TSDoc into model context. Exposed tool
   definitions reach the model; skill metadata advertises guidance for on-demand
   reading. Check the actual exposed definitions, not just files on disk.
2. **Make normal calls self-contained.** Tool descriptions and parameter schemas
   must explain correct invocation and consequential effects, including costs,
   authority, cancellation and uncertain outcomes where relevant. Do not hide
   essential cautions only in comments or a README.
3. **Keep the README very compact.** Include purpose, prerequisites, how to load
   or begin, a minimal workflow/example and essential limitations. It should let
   an agent start safely without reading the implementation. Link to local code
   for deeper questions; avoid architecture narration and duplicate API catalogs.
4. **Add a small usage entry point when needed.** A companion skill should say
   when to use the extension, tell the agent to read its installed README before
   first use, and explain how to locate that active bundle. Account for project,
   configured user and explicit/package locations; never assume a checkout path
   works after installation. Skill availability does not prove tool readiness or
   authorize installation. Skip a companion skill for genuinely self-explanatory
   capabilities; do not create generic runtime skills merely for symmetry.
5. **Keep deeper contracts beside code.** Use focused TSDoc for public behavior,
   invariants, limits and non-obvious failure/lifecycle semantics. Explain why,
   not each line. Prefer executable schemas and constants over another prose
   field list; do not require source reading for routine operation.
6. **Verify the delivered surface.** Check discovery, installed README/code links,
   exposed tools and packaging with the relevant offline tests. Exercise lifecycle
   and failure behavior when code changes; distinguish doubles from live evidence.
   Keep factories resource-free and cleanup idempotent. Installation, global sync,
   reloads, external connections and live model trials need their own authority.

Give each fact one primary owner, with short reminders at consequential actions.
This is authoring guidance, not a usage skill for a particular extension.
