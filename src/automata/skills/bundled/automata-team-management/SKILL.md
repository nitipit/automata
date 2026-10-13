---
name: automata-team-management
description: Use for coordinating delegated children, consolidating team status, adapting assignments or recovering manager loss. Not for individual message delivery.
---

# Automata Team Management

Own aggregate progress and continuity within the approved team envelope.

1. **Keep accountability explicit.** Each subtree has a named manager. Manage direct
   children and use their rollups for descendants; do not bypass parents to command
   grandchildren. Non-root managers report to their parent; only the root consolidates
   user reports. Peer discussion need not follow the reporting tree, but grants no
   assignment, file ownership or acceptance rights. Do not leave work unowned or
   treat status reports as acceptance or extra authority.

2. **Report useful evidence.** Base estimates on child evidence, remaining work,
   dependencies and uncertainty; distinguish observation from inference and work
   from waiting. Report meaningful changes or agreed deadlines, not activity.
   Timestamp persistent aggregate and child evidence; label stale/missing coverage.
   Token totals need source, window, as-of time and coverage, not invented telemetry.
   A blocked report names needed input from the parent or user at the root; one
   blocked branch or ordinary waiting need not block the whole subtree.

3. **Maintain visibility without polling.** Keep user-report commitments separate
   from evidence deadlines. Use callbacks and a reachable coordinator wake path with
   bounded adaptive fallback; synchronous work needs no watchdog. Overdue evidence
   allows bounded diagnosis of owned children, preferring messages/artifacts then
   metadata and one capture—not repeated inspection or completion inferred from activity.
   During alignment, queue routine updates; interrupt only for urgent safety,
   time-sensitive effects, invalid scope or immediate decisions. Cancel obsolete
   triggers on completion/pause; late evidence is not resume authority.

4. **Respect delegation limits.** Initial delegation needs a user/parent envelope.
   Missing `depth` is `0`; missing `child_limit` allows no children. Each descendant
   level consumes depth; child depth cannot exceed parent remaining depth minus one,
   child limits cannot exceed the parent's, and scope stays equal or narrower.
   Spare capacity grants no permission. Launch, replace and rebalance within the
   envelope without per-worker approval; expanding it requires a new approved one.
   Adapt using current evidence and verified ownership transfers. Authorized peers
   may discuss dependencies directly, not assign work, expand scope or contact
   unrelated agents. Keep consequential decisions and completion with the manager.

5. **Recover manager loss explicitly.** Loss is not a missed worker callback. Pause
   affected new work unless safe bounded continuation was authorized; preserve
   results and report through the parent chain, or to the user at the root.
   Descendants cannot assume manager authority. Read `references/manager-recovery.md`
   before transfer or resumption; recovery is parent-owned.

Planning owns review/evidence timing; delegation owns individual handoff and
acceptance. Transport, timer, model and lifecycle mechanisms stay with their owners.
