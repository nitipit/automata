---
name: automata-javascript
description: Use for JavaScript or TypeScript coding, debugging, testing, packaging, dependency management, linting, type checking, build tooling, or project workflow tasks.
---

# Automata JavaScript

## Purpose

Follow the repo's existing JavaScript/TypeScript conventions first.
If the repo does not make them clear, use the defaults below.

## Stacks

Use the repository's existing JavaScript/TypeScript workflow when it is clear.
Otherwise prefer `pnpm` for package and script execution, `pnpm dlx` for one-off
tool execution, and fall back to `npm` / `npx` when `pnpm` is unavailable or
unsuitable.

## Implementation Behavior

Inspect project conventions before changing code. Make targeted, local-style
changes and run the most relevant available checks after editing. Do not change
dependencies, lockfiles, Node versions, build setup, or package-manager setup
unless needed or confirmed.

## Boundaries

- Do not override documented repository tooling with the defaults in this skill.
- Do not treat JavaScript-specific defaults as general guidance for non-JavaScript
  projects.
