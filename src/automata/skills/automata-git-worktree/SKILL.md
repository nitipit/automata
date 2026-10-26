---
name: automata-git-worktree
description: Use for isolated Git checkouts, parallel branch work, or creating, integrating, recovering and retiring linked worktrees.
---

# Automata Git Worktree

Use worktrees when separate files provide useful isolation; otherwise keep the
current checkout. A worktree is not a sandbox: Git refs/configuration and external
services remain shared.

1. **Establish ownership and placement.** Confirm repository, owner, base revision,
   branch and allowed effects. Inspect checkout and registrations:
   ```bash
   git rev-parse --show-toplevel --git-common-dir
   git status --short --branch
   git worktree list --porcelain
   ```
   Reuse only matching identity, state and ownership; a clean directory can still
   be active. Follow approved placement conventions. The fallback is the owning
   checkout's `.agents/var/task-space/<task-name>/worktree/`, not each new worktree.
   Check occupancy, symlinks, Git ignore and build/watch/serve/cleanup behavior.
   Ignore rules alone do not ensure safety. Agree on another location if needed;
   do not change ignore rules or invent a global root without authority.

2. **Create and verify.** Choose a verified base and non-conflicting branch/path:
   ```bash
   git worktree add -b <new-branch> <path> <verified-base>
   ```
   Check existing branch occupancy; do not substitute remote defaults, fetch without
   authority, force/reset collisions or stash/move another owner's edits. Detached
   HEAD suits disposable checks if resulting commits are preserved. Verify repository,
   registration, HEAD and branch after creation; use explicit CWD or `git -C <path>`.
   Linked `.git` need not be a directory. After interruption inspect registrations,
   branches and files before retrying.

3. **Prepare only needed state.** Read applicable instructions and reuse verified
   recipes. Worktrees contain tracked files, not another checkout's dependencies,
   installations, secrets or runtime state. Do not copy `.git`, credentials or whole
   environments; check isolation before sharing writable build/dependency state.
   Installs, services and shared configuration retain their permission boundaries.

4. **Verify and integrate.** Keep ownership, revision, checks, integration target and
   pending cleanup in task state; Git already owns the registry. Verify locally
   before integration. Creation does not authorize commits, merges, rebases,
   cherry-picks, pushes or branch deletion. Recheck target state and coordinate its
   writer within integration authority; preserve unrelated work and verify results.
   Prefer merging a reviewed task branch when integrating its complete accepted work.
   Use cherry-picking only when deliberately selecting individual commits rather than
   integrating the branch, and explain that choice. Verify the combined result after
   integration. Distinguish tested, committed, integrated and published work.

5. **Retire safely.** Completion is not removal permission. Confirm exact registration,
   inactive users/processes and valuable tracked, untracked or ignored files and
   unpreserved commits. Clean status or a merged label proves neither disposability
   nor preservation after squash/cherry-pick. Preserve needed work at an approved
   location or durable ref, then use `git worktree remove <path>` and verify the
   outcome. Inspect refusals; do not bypass them with force or recursive deletion.
   Branch deletion needs separate authority. Use Git for moves and repair; missing
   paths may be offline volumes. Preview pruning and protect other registrations.
   Locks are not write ownership. Never retire merely because of age or task status.

6. **Retain useful setup knowledge.** Keep verified placement, prerequisites, commands
   and recovery limits outside the package under project
   `.agents/var/skills/automata-git-worktree/`; use the global equivalent only for
   explicitly global conventions. Keep live handles with task state, not recipes.
   Refer to authoritative configuration; never save secrets or universalize one
   task's path. Recheck affected assumptions after relocation, tooling or environment
   changes. Update within storage authority; saved commands grant no permission.

This skill owns worktree lifecycle, not team design, agent launches or publication.
