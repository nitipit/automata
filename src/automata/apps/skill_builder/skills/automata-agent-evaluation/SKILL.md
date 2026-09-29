---
name: automata-agent-evaluation
description: Use when behaviorally evaluating an agent's runtime behavior with fresh sessions, realistic scenarios, boundary checks, and observable evidence.
---

# Automata Agent Evaluation

Evaluate whether an agent behaves as intended in the runtime where it will be used. The
subject may be a new or changed skill, tool use, coordination, or another judgment boundary.
Treat this as behavioral evidence, distinct from frontmatter checks, package tests, prose
review, or confidence based only on reading instructions.

Use live-agent evaluation when activation, judgment, safety boundaries, tool use,
coordination, or failure recovery materially matters. Prefer ordinary automated checks for
purely mechanical changes. A low-risk wording correction does not need an agent experiment
unless its behavioral effect is uncertain.

## Evaluation Contract

Before running an agent, identify a set of observable claims and failure risks. Keep the agent
under test separate from the evaluator that owns the rubric, evidence, and verdict; subject
self-report is not self-verification. Test enough scenarios to resolve the claims:

- a natural positive request that should produce the intended behavior
- a nearby request that should not trigger it when false activation is a risk
- a boundary, missing prerequisite, ambiguous input, or failure condition
- a realistic successful path that produces the meaningful outcome

These are options, not a matrix; select from the change and plausible failures.

Use a fresh, unprimed session with normal project instructions and capability discovery. Record its
instructions, skills, tools, extensions, and runtime boundary. For automatic activation, phrase the
task naturally, allow normal read-only discovery of applicable instructions, skills, and
capabilities, and do not name the skill. A prompt that prohibits such inspection cannot establish
activation failure; classify it as a harness confound/failure or inconclusive. Explicit loading
tests post-activation behavior, not discoverability.

Keep prompts realistic and outcome-oriented. Do not reveal the expected workflow, phrases, or
verdict criteria; that tests prompt compliance rather than behavior. Provide only normal
permissions, safety limits, resources, and task facts.

Confirm runtime cost and consequential side effects before spawning agents unless already
authorized. Treat approved session, run, model, time, and cost limits as a hard budget; every
probe and retry consumes it. With only one fresh run, choose the highest-value scenario rather
than a warm-up; a harness-level failure is inconclusive and does not justify a silent retry.

For multi-agent evaluation, prefer tmux when participants share a server and exact owned targets
are available. Keep evaluator and subjects in dedicated detached sessions, with concise callbacks
and adaptive watchdogs for the next meaningful evidence. Keep raw traces disposable and send only
bounded evidence through tmux. Use direct synchronous execution for truly short, predictably
bounded tests, or agree on another transport when tmux is unavailable. This is contextual, not a
fixed terminal topology.

Use a disposable workspace for mutation tests; keep real-project evaluation read-only unless
writes are confirmed. Never expose secrets or use production accounts for realism.

## Coordinator Preflight

Before launching any subject agent or multi-agent runtime, write a compact run contract in the
plan and treat it as a launch gate:

- coordinator and each fresh subject, with responsibility and owned context;
- subject source or installation, runtime, model, and supported thinking effort;
- active agent-time and wall-clock estimate with its calculation basis;
- disposable workspace and allowed side effects;
- whether scored results will be retained and their owner-scoped destination;
- exact return path for every expected callback, or the agreed alternate transport;
- worker-to-coordinator watchdog owner, notification path, next expected evidence, and
  recovery action;
- coordinator-to-user watchdog owner and a supported user-visible notification path; and
- cleanup owner and stop condition.

Apply the contract to the evaluator itself. Resolve the team, transport, model, effort, estimate,
the disposition of both watchdog paths, and cleanup fields before launching the first subject or
starting a persistent runtime. A fully bounded synchronous-return run contract may record both
watchdog paths as `not applicable — bounded synchronous return`. Supported worker-to-coordinator
and coordinator-to-user watchdog paths, including the user-visible notification path, remain
mandatory for asynchronous or persistent subjects. After launching it, require direct verification
of the first subject's actual CWD, model/effort, discovered source or installation, and isolation
boundary against the contract before launching remaining scenario probes. If runtime identity
differs from the contract, stop remaining launches and classify the evidence rather than consuming
the budget in the wrong runtime.
A timer log, evidence file, or shell exit is not a user notification. If the coordinator cannot
wake the user-facing session through a supported path, say so and replan before long-running
asynchronous work.

For asynchronous work, return control to the caller only after the coordinator-to-user path is
established. Do not use `sleep`, blocking shell timeouts, or unbounded polling for coordination.
Use the agreed timer/watchdog path to record bounded evidence, then inspect, cancel, re-arm, or
recover normally. A hard process limit is a separate safety backstop, not a watchdog, callback,
or user notification.

## Evidence, Scoring, and Results

Prefer direct traces, diffs, receipts, artifacts, and command results over self-report. Extract
only the bounded evidence needed to reproduce or explain the result; do not ingest hidden or
encrypted reasoning, raw event streams, or full nested transcripts. Classify a failure as
behavior, activation, harness, environment, or inconclusive before revising the subject. Never
repair the subject inside a run and then count that run as a pass.

Report `PASS`, `FAIL`, or `INCONCLUSIVE` for each claim with its scenario, runtime, expected
behavior, evidence, classification or limitation, and smallest follow-up. One clean run is only a
smoke test; repeat only when justified within the accepted budget.

For scored or comparative evaluation, follow `references/scoring.md` before finalizing the rubric
or launching the subject. When result retention is accepted, start from
`templates/evaluation-record.json` and save one valid run beneath the applicable agent-data owner
directory. Do not count harness or environment failures as agent-ability history.

Clean up disposable sessions, workspaces, timers, background processes, raw traces, and generated
test artifacts after extracting evidence. Retain only accepted scored records, reports, or
fixtures.

## Boundaries

- Do not replace deterministic tests with agent experiments when code or schema checks can
  establish the behavior directly.
- Do not lead the test agent by embedding the expected behavior in the prompt.
- Do not treat explicit skill loading as proof of automatic activation.
- Do not infer success from confident prose or self-reported compliance without observable
  evidence.
- Do not bypass an installed-runtime contract by substituting a package source path and then
  count that result as runtime success; classify the missing installation or mapping instead.
- Do not exceed an explicit run, session, cost, or time budget while probing or retrying the
  harness.
- Do not prescribe a fixed model, agent harness, role, terminal topology, or communication
  chain; select an available isolated runtime appropriate to the scenario.
- Do not commit, push, install globally, or leave runtime state as part of evaluation unless
  the user separately authorizes that effect.
