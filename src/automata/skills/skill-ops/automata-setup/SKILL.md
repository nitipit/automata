---
name: automata-setup
description: Use when installing, exposing, or updating skills from bundled or custom sources, installing Automata tools or Pi extensions, or preparing a global or repo-local agent environment for use.
---

# Automata Setup

Install or expose skills and Automata runtime assets through the `automata` CLI, and clarify
whether the user also wants selected capabilities ready to use. Installation and
capability readiness are different outcomes. Keep changes explicit, local, and
reversible; use existing installers rather than copying files manually or creating
another orchestration command.

## Scope

Resolve whether assets belong in the global agent environment or the current repository.
Reuse explicit scope and replacement approval; ask only for missing choices. Use these
default roots unless the user chooses custom paths:

| scope | skills | tools | Pi extensions |
| --- | --- | --- | --- |
| global | `~/.agents/skills` | `~/.agents/tools` | `~/.pi/agent/extensions` |
| repository | `.agents/skills` | `.agents/tools` | `.pi/extensions` |

For general setup, offer skills, tools, and Pi extensions together; respect an
explicit skills-only or other narrower request. Confirm selected assets before
making changes. Keep character composition separate: it renders
instructions rather than installing assets and needs its own confirmed configuration.

For a ready-to-use environment, identify the capabilities the user intends to use;
ask only if that is unclear. Offer relevant environment-dependent setup, not every
installed skill. Respect installation-only requests. Judgment-only skills do not
need a setup ceremony, and skills should not all acquire mandatory setup phases.

## Installation

1. Confirm source (bundled by default), scope, and destination roots.
2. Confirm selected resource types and names, or explicitly all discovered assets.
3. Inspect only the selected destinations to determine whether this is a first install or
   an update.
4. Confirm the install mode before running commands:
   - `copy`: selected destination directories must not exist
   - `replace`: remove selected existing destinations, then copy; do not merge
   - `symlink`: expose the local source without copying; destinations must not exist
5. Run the relevant `uv run automata` commands using bundled sources by default.
6. Verify the selected installed files and report roots, mode, and replacements.
   Distinguish files installed from skills/extensions discovered by the intended
   runtime; use a fresh session or supported reload when discovery needs checking.

Use `--source-root` for an explicitly chosen custom source; do not assume a checkout
path for bundled assets. Skill sources accept local paths and `file://` URLs. For
remote sources, first obtain a confirmed local source; the installer does not fetch
remote repositories.

Skill discovery finds `SKILL.md` recursively and installs each containing directory
by its directory name; source grouping directories are not exposed. Keep this a
copy/exposure operation, not a skill-content review or extra package-structure audit.

## Capability Readiness

Use the selected capability's own guidance to establish readiness. It owns acceptance
criteria, safe checks, runtime resources, reusable setup knowledge, and recovery.
This skill keeps the requested setup scope clear; it does not implement neighboring
capabilities or prescribe a fixed skill invocation chain.

Review relevant existing setup evidence before proposing changes. Agree on the
smallest useful verification and its allowed effects. Installation approval alone
does not authorize test messages, external actions, dependency installation,
configuration changes, or persistent processes. Reuse explicit permission already
covering those effects; ask only for uncovered scope. Do not launch workers merely
to make installation appear complete.

A file, executable, loaded tool, or open endpoint is not proof that the intended
capability works. For communication, a verified result includes intended receiver
handling and the return path when a response is required—not just a send receipt.
When a test is not authorized or prerequisites are missing, report what remains
untested or blocked rather than claiming readiness.

When reusable setup knowledge is useful, let its capability owner record it in the
approved data location, with scope, evidence, limitations, and reuse/invalidation
guidance. Do not require a setup record for every capability, create a central
readiness registry, or persist live handles as permanent identity. On later use,
revalidate changeable prerequisites and repair only the affected setup within
authority. Report installed assets separately from verified, untested, or blocked
capabilities; do not turn that distinction into a mandatory report template.

## CLI Usage

Install or update all bundled skills:

```bash
uv run automata skills install --target-root <skills-root> --mode <mode>
```

Select skills with repeatable or comma-separated `--skill` values. For example,
from a confirmed custom source:

```bash
uv run automata skills install \
  --source-root <local-path-or-file-url> \
  --target-root <skills-root> \
  --skill <skill-a>,<skill-b> \
  --mode <mode>
```

Omit `--source-root` for bundled skills. Omit `--skill` only when all discovered
skills are intended.

Install or update all bundled tools:

```bash
uv run automata tools install --target-root <tools-root> --mode <mode>
```

Install or update all bundled Pi extensions:

```bash
uv run automata pi-extension install --target-root <extensions-root> --mode <mode>
```

Run only commands for confirmed resource types. A symlinked asset reflects source
changes, so do not replace it merely to refresh content.

## Boundaries

- Do not install, replace, or symlink anything before the user confirms roots, selected
  resources, and mode.
- Do not edit `AGENTS.md`, compose character instructions, or modify installed asset
  contents as part of setup.
- Do not use `pi install`; that manages Pi packages, not Automata's local asset layout.
- Do not infer global versus repository scope from convenience; ask the user.
- Skill authoring and review belong to `automata-skill-design`, not installation.
