---
name: automata-python
description: Use for Python coding, debugging, testing, packaging, dependency management, linting, type checking, or project workflow tasks.
---

# Automata Python

## Purpose

Follow the repo's existing Python conventions first.
If the repo does not make them clear, use the defaults below.

## Stacks

Use the repository's existing Python workflow when it is clear. Otherwise prefer
the `uv` / `uvx` stack for Python runtime, dependency, and tool execution.

## Documentation Style

- Add or preserve module docstrings where they clarify a module's purpose,
  public behavior, or non-obvious design.
- Prefer concise, useful docstrings over boilerplate. Do not add redundant
  module docstrings to obvious scripts or tiny modules unless the repo's
  convention requires them.
- If a module docstring cannot explain the module's purpose and boundaries in
  an easily understandable way, treat that as a design signal. Before adding
  vague documentation, consider whether the module has unclear responsibilities,
  whether names should be improved, or whether functions/classes should be moved
  or split into better-scoped modules.

## Implementation Behavior

Inspect project conventions before changing code. Make targeted, local-style
changes and run the most relevant available checks after editing. Do not change
dependencies, lockfiles, Python versions, or packaging setup unless needed or
confirmed.

## Boundaries

- Do not override documented repository tooling with the defaults in this skill.
- Do not add dependencies, change packaging, or alter project workflow unless the task requires it.
- Do not treat Python-specific defaults as general guidance for non-Python projects.
