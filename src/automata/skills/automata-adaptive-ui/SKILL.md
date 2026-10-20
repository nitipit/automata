---
name: automata-adaptive-ui
description: "Use for designing or implementing web interfaces using the Adaptive UI reference: design tokens, typography, components and interaction examples. Not for browser control or unrelated backend work."
---

# Automata Adaptive UI

Study [Adaptive UI](https://github.com/keenlycode/automata-adaptive-ui) before
applying its design foundations. Use it as a reference, not a required dependency
or a replacement for the target project's requirements and design system.

1. **Read the current reference.** Consult its README through a local checkout or
   repository fetch. Read the relevant source rather than infer behavior from
   component names. If unavailable, report that limit instead of claiming to have
   studied it. Keep reference checkouts outside the target project's maintained
   source and treat them as read-only unless changes are explicitly requested.

2. **Study what the task needs.** Repository-relative starting points:
   - `src/browser/_ui/tokens/`: color, spacing, radius, effects and lift.
   - `src/browser/_ui/tokens/typography.ts`: type scales and reading styles.
   - `src/browser/_ui/components/`: component structure, states and behavior.
   - `src/browser/design/`: interactive token, typography and component examples.
   Follow the current README if these paths change. For visual or interaction
   questions, use an available preview or follow its current preview instructions
   within approved setup and process scope; source review alone is not visual proof.

3. **Adapt, do not blindly transplant.** Translate the relevant patterns into the
   target stack and reuse its existing tokens and components where suitable.
   Consulting the reference does not install a package or register custom elements.
   No dependency installation or preview server is needed for source-only study.

4. **Verify the result.** Check relevant layout sizes, typography, interaction
   states, keyboard use and accessibility in the target interface. Report what was
   adopted or deliberately changed and which visual or behavioral checks were
   actually performed.
