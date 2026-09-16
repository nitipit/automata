---
name: automata-web-browser-control
description: Use when automating a real browser, establishing a reusable control connection, or recovering browser interaction.
---

# Automata Web Browser Control

Control the intended browser through a verified setup recipe, discovering a new
method only when needed. This skill owns browser interaction, not application,
UI component, or visual asset creation.

## Find or establish working control

Consult relevant saved setup knowledge first and reuse its verified recipe rather
than reconstructing commands. On reuse, check only changeable prerequisites:
connection, browser/profile ownership, and target availability. Treat recorded
coordinates as hints to verify, not permanent identity.

If the recipe is absent or invalid, inspect available browsers, automation libraries,
connections, and display constraints. Choose the smallest reliable path that fits
the task; an unavailable tool is not proof that browser control is impossible.
Use visible control when the user needs to watch or participate. Resolve choices
that affect privacy, profiles, persistence, installation, or user control.

Verify the chosen connection and intended browser/profile ownership, then confirm
control through a bounded authorized action and observed result. Executable presence
alone is not a successful connection. Recover only the affected setup within existing
authorization; report blockers or unverified parts rather than claiming readiness.

## Save and reuse the recipe

After successful setup, save a reusable recipe in a suitable agent-data location
within approved owner-scoped data. Include verified launch or attach commands,
executable/library paths, profile policy, working directories and variable inputs,
a minimal control example, connection checks, cleanup procedure, limitations, and
invalidation conditions. Record what worked, not speculative alternatives; exclude
secrets and browser content. Reuse existing storage approval; if absent, ask before
saving. Report the recipe's location and update the recipe after verifying a changed
setup. Commands and environment-specific details belong there, not in this skill.

Keep live endpoints and process handles separate and temporary; saved knowledge
does not authorize future actions. Revalidate live identity before reuse rather
than treating a saved port or process ID as proof of ownership.

## Act, observe, and finish

Connect to the intended page, perform bounded actions, and verify actual browser
results; successful command execution alone is insufficient. Use screenshots or
other feedback as needed. Complete authorized multi-step work; do not stop after
each routine action. Pause for user-paced interaction, a consequential unresolved
choice, a blocker, or an action outside authority. Diagnose failures narrowly and
report setup changes or fallbacks.

Prefer temporary runtime locations outside the repository. Do not add automation
dependencies to a project unless it needs them. Keep persistent browsers managed
with identifiable ownership and a reconnect/cleanup path, not unmanaged background
processes. Retain them only when useful and authorized; otherwise disconnect and
stop only owned resources no longer needed. Report enough live connection and
ownership information for reconnection or cleanup.

## Boundaries

- Use isolated profiles for Chrome/Chromium, never the user's real/default profile.
  For Firefox, confirm default versus isolated profile use. Never silently switch
  profile policy or reuse another task's profiles, ports, or sessions.
- Confirm ambiguous targets. Require authorization for package installation, file
  creation, persistent browser launches, profile changes, or broader repairs.
- Require explicit instruction for credentials, form submissions, purchases,
  deletions, or account changes. Saved recipes do not authorize these actions.
- Read cookies, storage, passwords, form values, or account data only when requested
  or necessary for the confirmed task. Ask before inspecting sensitive pages,
  extracting full page text, or saving page content. Store sensitive browser content
  only when requested.
