---
name: automata-agent-data
description: Use when an agent, skill, or tool needs to create, read, organize, retain, or remove mutable data that supports agent operation, or when its accumulation warrants a retention review.
---

# Automata Agent Data

This skill governs agent operational data and disposable task work, not maintained
project source or user-owned data. When an Automata repository has no explicit agent-data convention,
store capability-owned agent data under `.agents/var/`:

```text
.agents/var/skills/<skill-name>/
.agents/var/tools/<tool-name>/
```

Choose the namespace from the capability that owns the data. Let that owner define
its internal layout. Do not create a generic shared directory merely because a
future use is possible.

## Precedence

1. Follow an explicit agent-data convention when one exists.
2. Otherwise use the Automata default above when a repository context is known.
3. Outside a repository context, ask before choosing durable storage.

## Task Workspaces

When no suitable task location is established, use
`.agents/var/workspace/<task-name>/` for disposable experiments, scratch files,
temporary dependencies, and results. Choose layout from the task and context;
this is a fallback, not a mandatory directory template. Keep capability-owned
state in its own namespace rather than duplicating it in each workspace.

Promote work into maintained source only within approved scope. Removing a
workspace may lose temporary work, but fresh repository operation must not depend
on it. Stop its owned processes before cleanup. Choose UI output and serving roots
as needed; serve only public-safe files, keeping credentials and private state
outside the served root. The entire workspace is not implicitly a public website.

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

- Keep packaged instruction components and skill or tool source outside agent-data
  directories.
- Do not modify or remove data owned by another skill or tool without confirmation.
- Ask before establishing a new shared or durable data convention that falls outside
  an existing owner directory.
