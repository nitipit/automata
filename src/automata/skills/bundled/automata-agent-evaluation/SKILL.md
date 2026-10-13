---
name: automata-agent-evaluation
description: Use for evaluating agent behavior, skill activation, judgment, safety or recovery in realistic runtime tasks. Not for ordinary software tests or prose review.
---

# Automata Agent Evaluation

Evaluate what an agent actually does in its intended runtime. Use behavioral runs
when judgment or interaction matters; use ordinary automated checks for mechanical
changes. Minor wording edits do not automatically need live evaluation.

1. **Define the claim.** Identify observable outcomes and failure conditions before
   running. Choose relevant positive, nearby non-matching or adverse scenarios—not
   a mandatory test matrix. Keep the evaluator's rubric separate from the subject;
   do not reveal expected answers, phrases or workflows in its task prompt.

2. **Agree on limits.** Confirm the subject revision, runtime, model/effort,
   permissions, isolation, run/time/cost budget, evidence retention and cleanup
   authority. Include a proportionate time estimate. Every probe and retry counts
   toward the approved budget. Use disposable workspaces for mutations; real-project
   writes need permission. Do not expose secrets or production accounts.
   For asynchronous runs, establish ownership, a reachable callback and bounded
   fallback wake before launch. A log is not a wake-up path. Agree on reporting
   and cleanup; use the current chat unless external delivery is authorized.
   Bounded synchronous runs need no communication watchdog.

3. **Use an unbiased subject.** Start a fresh session with normal instructions,
   tools and discovery. Use natural requests; do not name the skill when testing
   automatic activation. Explicit loading tests behavior after activation, not discovery.
   Verify actual CWD, model/effort, installed or source revision and isolation before
   further launches. Do not substitute source for a required installed-runtime test.
   Stop remaining launches if the runtime differs from the agreed setup.

4. **Observe and classify.** Judge tool calls, receipts, artifacts and useful outcomes,
   not confidence or self-reported compliance. Keep evidence bounded; do not ingest
   hidden reasoning or full nested transcripts. Classify failures as behavior,
   activation, harness or environment; use inconclusive when evidence cannot decide.
   Preventing normal discovery invalidates an activation-failure claim. Never repair
   a subject during a run and relabel that same run as a pass. For asynchronous work,
   yield when idle and reassess on callback or fallback wake; do not block or poll
   endlessly. A process timeout is a safety backstop, not a notification path.

5. **Report and stop.** Report each claim as `PASS`, `FAIL` or `INCONCLUSIVE`, with
   scenario, runtime, evidence and limits. One run is a smoke test, not proof of
   repeatability. Repeat only for a concrete reason within approved budget; harness
   failure does not justify a silent retry. For scored or comparative runs, read
   `references/scoring.md` before defining the rubric or launching. Retain records
   only when approved, using `templates/evaluation-record.json`; do not count harness
   or environment failures as agent-ability history. Cancel obsolete wake triggers
   on completion or pause; late callbacks do not authorize resuming. Clean up only
   owned resources covered by cleanup permission, preserving accepted evidence.
   Evaluation does not authorize commits, pushes, global installs or extra effects.
