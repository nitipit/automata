# Hierarchical teams

Use for nested delegation, subtree accountability or manager loss. Flat handoffs
need no reporting hierarchy beyond their named owner and acceptance authority.

## Preserve the delegation envelope

Each subtree has a named manager. Missing `depth` is `0`; missing `child_limit`
allows no children. Each descendant level consumes depth; child depth cannot
exceed the parent's remaining depth minus one, and child limits cannot exceed the
parent's. Scope stays equal or narrower. Spare capacity grants no permission.
Launch, replace or rebalance within the approved envelope; expanding it needs new
approval. Use verified ownership transfers, not implied authority from a launch.

## Coordinate through accountable owners

Manage direct children and use their rollups for descendants; do not bypass a
parent to command grandchildren. Non-root managers report to their parent; the
root consolidates user reports. Authorized peers may discuss dependencies directly,
not assign work, transfer file ownership, accept results, expand scope or contact
unrelated agents. A status report is neither acceptance nor new authority.

Base aggregate estimates on child evidence, remaining dependencies and uncertainty.
Distinguish work from waiting and label stale or missing coverage. A blocked report
identifies the needed input from the parent, or from the user at the root. One
blocked subtree does not necessarily block unrelated work.

## Recover manager loss

Manager loss is different from a worker missing a callback. Pause affected new
work unless bounded continuation was authorized; preserve results and report up
the parent chain, or to the user at the root. Descendants cannot appoint themselves
manager or silently resume. Read [manager recovery](manager-recovery.md) before
replacement, reparenting or closure; that decision belongs to the parent/user.
