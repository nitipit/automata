---
name: automata-ui-design
description: "Use for designing, implementing or reviewing user interfaces: task flows, information hierarchy, visual systems, interaction states, accessibility and responsive behavior. Not for browser operation or backend-only work."
---

# Automata UI Design

Design for the user's task, not just the appearance. Reuse the project's existing
visual language and components before introducing another system.

1. **Find the consequential gaps.** Identify the intended users, primary actions,
   content hierarchy and constraints. Discuss unresolved choices that affect the
   experience or architecture; do not turn every small change into a questionnaire.
2. **Design behavior with appearance.** Keep typography, spacing, color and controls
   coherent. Account for relevant loading, empty, error and success states,
   keyboard/focus behavior, accessibility, motion and different viewport sizes.
3. **Separate design responsibilities.** Tokens express shared design decisions;
   components use tokens to provide reusable structure and behavior; pages/scenes
   compose components and may also use tokens directly for layout and styling.
   Adapt these responsibilities to the target technology and existing project
   conventions, not fixed folder names or APIs. Discuss unclear ownership before
   introducing a competing structure. The [web example](references/web-ui.md)
   illustrates one implementation, not a required stack or permission to scaffold
   or migrate.
4. **Verify the experience.** Check relevant rendered layouts and interactions;
   source review alone is not visual proof. Report what was actually checked and
   what remains unverified. Browser operation and engineering mechanics retain
   their own guidance.
