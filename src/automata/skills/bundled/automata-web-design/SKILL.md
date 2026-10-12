---
name: automata-web-design
description: Use when creating or revising websites and browser interfaces, designing UI, integrating web applications, or building and previewing them. Selects relevant nested UI or application guidance; not general browser automation.
---

# Automata Web Design

Connect the intended user experience to a working web application. Keep design,
reusable UI and application integration coherent without making every task load
all implementation guidance. Respect an existing stack and approved scope.

## Start with the experience

Identify what the user needs to see, decide or change, and the smallest useful
interaction that demonstrates it. Separate exploratory design from production
requirements. Agree on consequential design choices before implementing them;
do not introduce backend state or a framework just to make a visual idea tangible.

## Select the relevant child

Resolve these paths against this skill directory. Read a child's `SKILL.md` when
its responsibility is needed; the directory hierarchy does not imply automatic
loading or an obligation to read both.

- `skills/automata-adaptive-ui/SKILL.md`: interface composition, shared tokens and
  components, interaction/state ownership, and UI draft/preview decisions.
- `skills/automata-web-app/SKILL.md`: application routes, templates, integration,
  project creation, frontend builds and backend serving.

For UI-only or application-only work, the relevant child can stand alone. For
end-to-end work, carry the selected UI composition and its data contracts into
application integration rather than redesigning them at each layer.

## Connect the layers

Keep reusable UI behavior and primitive values in the UI library; keep page
composition, routes and backend state in the application. A task-local component
does not become a library component merely because it appears in a preview.
Reuse the children's maintained examples and public interfaces instead of copying
another foundation into the parent. Their directories remain siblings inside
`skills/`, so the web-app example can resolve its Adaptive UI source dependency.

Reuse an owned preview where suitable. Distinguish maintained source, generated
browser assets and live browser state; a successful build is not proof of a good
experience. Verify the integrated result with a bounded browser check appropriate
to the agreed goal. Report design choices and unverified boundaries without
claiming production readiness from an exploratory demonstration.

## Boundaries

This skill owns the design-to-application connection and layer decisions, not the
children's mechanical APIs. Installation, browser control, process lifecycle and
external integrations retain their own authority. Grouping skills grants no
permission to install dependencies, launch services or promote a draft.
