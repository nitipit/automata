---
name: automata-task-space
description: Use for placing, organizing, sharing, resuming or cleaning task-specific workspaces, experiments and temporary project copies. Not for reusable capability state.
---

# Automata Task Space

Keep task drafts, experiments, dependencies, outputs and evidence together. Reusable
capability state stays with its owner; Git owns worktree creation and lifecycle.

1. **Choose a suitable location.** Reuse approved conventions and suitable areas.
   Otherwise use repository-local `.agents/var/task-space/<task-name>/`; no workspace
   is mandatory for every request. Ask before storage outside approved scope.
   Check contents, ownership and symlinks before reuse. Nested scratch must be ignored
   and excluded from unintended builds, watchers, serving and cleanup; Git ignore
   alone is insufficient. Choose another suitable authorized location rather than
   silently editing configuration.

2. **Keep ownership and layout clear.** A workspace belongs to the task, not one
   agent. Coordinate shared writes and handoffs; avoid duplicate working copies.
   Separate inputs, useful evidence and disposable outputs without fixed templates
   or empty bookkeeping. Serve only public-safe preview files, never private state,
   credentials or the whole task area.

3. **Preserve continuity.** Leave enough context to find artifacts, understand decisions
   and checks, and resume pending work. Reuse owner records instead of duplicating
   them. Promote outputs only within authority; normal project operation must not
   depend on scratch files.

4. **Retire safely.** Completion/age is not cleanup permission. Identify owned inactive
   candidates and preserve valuable edits, inputs and evidence. Stop owned processes
   and retire managed resources through their interfaces before deleting containers:
   remove registered worktrees with Git, not directory deletion. Each action retains
   its authority boundary. Prefer recoverable removal; do not touch another owner's
   data or follow links beyond scope. Ask when authority is unclear.
