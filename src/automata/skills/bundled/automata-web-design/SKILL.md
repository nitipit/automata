---
name: automata-web-design
description: Use for designing websites/browser interfaces and connecting UI with application integration. Select relevant nested guidance; not general browser automation.
---

# Automata Web Design

Connect the intended experience to a working application while respecting the
existing stack and approved scope.

1. **Start with the experience.** Identify what the user needs to see, decide or
   change and the smallest useful interaction. Separate exploration from production
   requirements. Align on consequential choices; do not introduce frameworks or
   backend state merely to demonstrate a visual idea.

2. **Select only relevant guidance.** Resolve children relative to this directory;
   hierarchy does not load them automatically:
   - `skills/automata-adaptive-ui/SKILL.md`: components, tokens, interaction/state,
     UI drafts and previews.
   - `skills/automata-web-app/SKILL.md`: routes, templates, project setup, builds
     and serving.
   Either child can stand alone. For end-to-end work carry UI/data contracts into
   integration instead of redesigning each layer.

3. **Keep layers coherent.** Reusable behavior/primitives belong in the UI library;
   page composition, routes and backend state belong in the app. Local preview
   components are not automatically catalog additions. Reuse public contracts and
   maintained examples, not another foundation. Keep children as siblings so example
   source dependencies resolve.

4. **Verify the experience.** Reuse suitable owned previews. Distinguish maintained
   source, generated assets and live browser state; builds prove no design quality.
   Check relevant integrated browser behavior and report unverified limits, not
   production readiness from a demo.

Grouping grants no installation, service-launch or promotion authority. Browser
control, process lifecycle and external integrations retain their own boundaries.
