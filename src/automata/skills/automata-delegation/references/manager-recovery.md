# Manager recovery

Use when a manager is lost or unavailable, not when a worker misses a callback.
Missing worker evidence belongs to that caller-to-worker delegation contract.

## Preserve and report

Pause new work in the affected subtree unless safe, bounded continuation was
explicitly authorized. Preserve completed and partial results, current state,
envelopes, dependencies, estimates, risks, correlation identifiers and pending
decisions. Do not discard, duplicate or silently accept work during recovery.

Report the loss and paused work to the direct parent; at the root, report to the
user. Escalation climbs parent-by-parent. Non-root nodes do not bypass their parent
to report directly to the user, even when that parent's response is unavailable.
Keep evidence available rather than appointing a replacement yourself.

## Establish the recovery decision

Recovery is parent-owned; the user owns the decision when there is no parent.
Record one explicit outcome:

- **Replacement:** appoint a new manager and reissue the applicable envelope.
- **Reparent:** move a direct child to a named parent with a compatible envelope;
  notify affected participants.
- **Closure:** stop the subtree, recording final evidence, unresolved risks, reason,
  acceptance state and a named cleanup owner.

Until the decision is explicit, descendants cannot assume authority or resume
unauthorized work. Preserve visibility and continuity: recovery must not silently
transfer responsibilities, timers, model choices, communication paths or ownership.
Use the delegation contract for the actual handoff, including pending evidence and
lifecycle obligations. A replacement's launch alone does not complete the transfer.
