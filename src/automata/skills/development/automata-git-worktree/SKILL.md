---
name: automata-git-worktree
description: Use when a task needs an isolated Git checkout, parallel branch work, or creation, reuse, integration, recovery, or cleanup of linked worktrees.
---

# Automata Git Worktree

Use linked worktrees when separate working files help the task: concurrent branch
work, an isolated experiment, or verification without disturbing ongoing edits.
Stay in the current checkout when separation adds no useful protection. A worktree
is not a sandbox: Git objects, refs and much configuration are shared, and external
services, permissions and side effects remain outside its isolation.

## Establish ownership and placement

Identify the repository, task owner, intended base revision and branch, and the
allowed effects. Inspect the current checkout and registered worktrees before
creating another. Useful read-only starting points are:

```bash
git rev-parse --show-toplevel --git-common-dir
git status --short --branch
git worktree list --porcelain
```

Resolve paths against the checkout that produced them; do not assume `.git` is a
directory in a linked worktree. Reuse an existing worktree only when its identity,
branch, state and ownership match the task. A clean checkout is not evidence that
no other agent, editor or process is using it. Coordinate ownership before sharing
writes or taking over another task's directory.

Consult relevant placement/setup knowledge first. Follow an established project
or approved user convention. Without one, use a suitable task workspace; the
repository-local fallback is `.agents/var/workspace/<task-name>/worktree/`, resolved
from the task's owning repository checkout, not repeatedly from each new worktree.
Do not put working checkouts in the skill package or recipe directory.

Before using a nested location, verify it is ignored by the containing repository
and will not be recursively built, watched, served or cleaned by project tooling.
For a selected path, `git check-ignore -v -- <path>` can verify the Git ignore rule;
it does not establish tooling safety. Check destination occupancy and symlink
resolution so the path cannot overwrite or escape into someone else's workspace.
If nesting is unsuitable, agree on an external location unless an existing approved
convention already covers it. Do not silently edit ignore rules, invent a global
worktree root, or relocate existing work.

## Create or reuse the checkout

Within authorized scope, choose the exact base and a non-conflicting branch/path.
Do not silently substitute a remote-tracking default or assume it is current; fetch
only when needed and authorized. For a new task branch, the command shape is:

```bash
git worktree add -b <new-branch> <path> <verified-base>
```

Use an existing branch only after checking that it is the intended branch and is
not checked out elsewhere. Detached HEAD can suit a disposable read-only check,
but retain any resulting commits before retiring it. Avoid `-B`, forced checkout,
or branch resets to resolve collisions. Stop and resolve ownership or choose an
available name within scope instead.

After creation, verify the registered path, repository identity, HEAD/base and
branch before modifying files. Run subsequent commands with an explicit working
directory, such as `git -C <path> ...`, rather than relying on a prior shell's CWD.
Do not move another checkout's uncommitted changes or automatically stash them.
If the operation fails or is interrupted, inspect the registration, branch and
filesystem state before retrying; do not assume nothing was created.

Establish only the environment needed for the task. A worktree contains the selected
revision's tracked files, not another checkout's untracked or ignored dependencies,
local skill installations, secrets or runtime state. Read its applicable project
instructions and reuse relevant setup recipes. Do not copy the other checkout's
`.git`, credentials or whole environment, or share writable dependency/build state
without checking isolation. Dependency installation, service startup and shared
configuration changes retain their own authorization boundaries.

## Work and integrate

Keep the task's path, branch or detached revision, ownership, meaningful validation,
integration target and outstanding cleanup with its existing task state. Do not
create a central worktree registry that duplicates Git's registration. Recipes
are reusable setup knowledge, not live ownership records.

Verify the change in its own checkout before proposing integration. Committing,
merging, rebasing, cherry-picking, pushing and deleting branches are separate
effects; creation permission does not imply all of them. Within integration
authority, recheck the target's current state and coordinate its writer before
applying changes. Preserve unrelated work, resolve conflicts without broadening
scope, and verify the resulting target state. Report tested changes separately
from committed, integrated or published changes.

## Retire and recover safely

Task completion does not authorize removal. Before an authorized cleanup, identify
the exact registered worktree and establish that its users and owned processes are
inactive. Check tracked modifications, untracked files, valuable ignored files,
and branch or detached commits not preserved at the intended destination. Default
status output omits ignored files; a clean result is not proof of disposability.
Do not rely on a merged label alone after squash/cherry-pick integration.

Preserve needed work and evidence through an approved recovery location or durable
Git reference before removing the directory. Then use `git worktree remove <path>`
within removal authority and verify both registration and filesystem outcome.
Git's refusal to remove is a reason to inspect, not to retry with `--force` or use
recursive deletion. Branch deletion is separate; retain branches unless their
deletion is also authorized and their work is accounted for.

Use Git's worktree mechanisms for authorized moves and metadata repair rather than
manually editing `.git` links. A missing path may be an offline volume, not an
abandoned checkout. Preview pruning before any approved metadata cleanup; pruning
can affect multiple registrations and must not discard another owner's recovery
state. Locks protect registration from some Git operations, not concurrent writes
or permission boundaries. Review accumulating worktrees at task handoff or cleanup
boundaries; never remove them automatically because of age or a terminal status.

## Retain setup knowledge

Store useful verified placement and setup recipes outside the package, normally
under `.agents/var/skills/automata-git-worktree/` in the owning repository. Use
`~/.agents/var/skills/automata-git-worktree/` only for explicitly global conventions.
Make knowledge findable by project or purpose; no fixed schema or per-task recipe
is required. Keep operational handles and task progress with their task owner.

After useful discovery, retain the applicable location convention, prerequisites,
verified commands, evidence, limitations and cleanup/recovery considerations within
storage authority. Refer to authoritative project configuration instead of copying
it. Do not persist secrets or mistake a task's chosen path for a universal default.

On later use, revalidate assumptions affected by repository relocation, changed
ignore/build rules, Git behavior or environment setup. Repair only invalid parts;
saved commands do not grant permission. Preserve unrelated knowledge when updating
recipes and review stale or conflicting guidance within cleanup authority.

This skill owns worktree lifecycle and placement, not team design, agent launches,
project build procedures or publication policy. Compose those responsibilities as
the task requires without prescribing a skill invocation chain.
