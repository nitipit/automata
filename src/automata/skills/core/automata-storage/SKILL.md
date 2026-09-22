---
name: automata-storage
description: Use when choosing locations, ownership, retention, or cleanup for capability-owned operational data or task workspaces.
---

# Automata Storage

Choose storage by ownership and lifecycle, not on every file read or write. This
skill governs agent operational data and work artifacts, not arbitrary management
of maintained project source or user-owned files.

- Capability-owned data supports continuing use: reusable runtimes, profiles,
  setup recipes, and tool state.
- Work-owned data supports a particular task: drafts, experiments, trial-only
  dependencies, generated artifacts, and evidence. A skill producing a file does
  not automatically make that file capability-owned.

When no explicit storage convention applies, use these repository-local defaults
for capability-owned data:

```text
.agents/var/skills/<skill-name>/
.agents/var/tools/<tool-name>/
```

Choose the namespace from the capability that owns the data. Let that owner define
its internal layout. Shared skill/tool data needs one owner, not duplicate copies
or a central storage-skill directory. Do not create a generic shared directory
merely because a future use is possible.

## Precedence

1. Follow an explicit storage convention when one exists.
2. Otherwise use the repository-local defaults when a repository context is known.
3. For explicitly global capabilities, use the equivalent paths under
   `~/.agents/var/`. Without an established scope, ask before choosing durable
   storage outside a repository.

These defaults do not authorize installation, scope expansion, or moving existing
files. Keep existing locations unless a migration is needed and authorized.

## Task Workspaces

Reuse a suitable working area. Otherwise, `.agents/var/workspace/<task-name>/`
is a fallback for work-owned data, not a mandatory template or a new directory
for every request. A workspace belongs to the work; agents may share or hand it
over. Keep capability-owned state with its owner rather than copying it into
individual workspaces.

Workspaces may contain valuable edits and evidence; completion does not make them
disposable. User-provided inputs remain user-owned. Promote work into maintained
source only within approved scope; normal project operation must not depend on
scratch work. Stop owned processes through their responsible capabilities before
cleanup. Serve only public-safe files, keeping credentials and private state
outside the served root; a whole workspace is not implicitly a public website.

## Setup Knowledge and Live State

Keep reusable setup knowledge separate from temporary runtime handles when their
lifetimes differ; separate files are optional. The capability owner defines validity
checks and recovery, not a central readiness registry. Save only knowledge worth
reusing within approved storage scope; do not copy secrets, authoritative project
configuration, or transient handles into a permanent source of truth.

## Growth and Retention

Treat retention as an ownership decision, not just a size check. Distinguish
rebuildable caches and disposable outputs from durable decisions, unique evidence,
and user-authored inputs. Keep different lifecycles separate; age alone does not
establish that data is safe to remove.

Follow the data owner's agreed growth and retention policy. At natural maintenance
boundaries, notice meaningful accumulation or rising navigation, storage, or read
cost. Use lightweight metadata or existing observations first, not recursive scans
on every write. If a review is warranted, explain what grew and offer a scoped
cleanup; avoid repeating unchanged notices after the user defers them.

Choose review triggers appropriate to the data's value and cost. There is no
universal file count, age, or byte quota. Distinguish a soft review threshold from
a hard limit: a reminder does not stop growth. A hard limit needs an agreed action
at the boundary, not silent eviction or data loss.

Identify exact owned candidates and effects before cleanup. A clear scoped removal
request or agreed automatic-retention policy can authorize cleanup; a growth notice
cannot. Ask when authority or scope is unclear. Prefer recoverable removal and
confirm permanent deletion unless explicitly authorized. Do not delete active data,
follow links into another owner's data, or remove referenced evidence merely because
it sits near disposable output. Ask before consolidating or relocating durable data
outside an already authorized maintenance policy.

## Boundaries

- Keep packaged instructions and skill/tool source separate from mutable data;
  package installation belongs to setup, not this skill.
- Planning, delegation, and process control remain with their existing owners.
- Do not modify or remove another capability's or task's data without authorization.
- Ask before establishing a new shared or durable data convention that falls outside
  an existing owner directory.
