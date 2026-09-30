---
name: automata-task-space
description: Use when choosing locations for delegated-agent work, Git worktrees, experiments, or temporary project copies; also when organizing, sharing, resuming, or cleaning up a task-specific working area.
---

# Automata Task Space

A task space holds task-specific drafts, experiments, temporary dependencies,
outputs, and evidence. Keep reusable capability state with its owner, not copied
into each task. Task-space guidance owns placement; Git-worktree guidance owns
creating and managing an isolated checkout at the chosen location.

## Choose and use

- Follow an established location convention and reuse a suitable working area.
  Otherwise, `task-space/<task-name>/` is a repository-local fallback,
  not a mandatory directory for every request. Ask before establishing storage
  outside the authorized scope.
- A task space belongs to the work, not one agent. Share or hand it over when
  useful; coordinate changes to shared files and avoid duplicate working copies.
- Use a simple layout that separates user inputs, useful evidence, and disposable
  outputs. Do not impose a fixed template or create empty bookkeeping files.
- For continuation, leave enough context to find relevant artifacts, understand
  decisions and validation, and identify remaining work. Reuse existing notes
  rather than duplicating authoritative project records.
- Serve only public-safe files for previews; the whole workspace is not a public
  website. Keep credentials and private state outside the served root.

## Promote and retire

Promote useful outputs into maintained locations only within approved scope;
normal project operation must not depend on scratch files.

Review accumulation at natural maintenance boundaries. Completion or age alone
is not deletion permission. Before authorized cleanup, identify exact owned
candidates, confirm they are inactive, and preserve valuable edits, evidence, and
user inputs. Stop owned processes through their responsible interfaces first.
Prefer recoverable removal; do not touch another owner's data or follow links
outside the cleanup scope. Ask when authority is unclear.
