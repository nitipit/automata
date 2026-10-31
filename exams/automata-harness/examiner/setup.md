# PRIVATE: Setup and evidence contract — package/setup v4 draft

Paper/key bundle revisions are 3: P04 question/key v2 now use prepared native RPC,
and K07 key v2 updates worker-control ownership after team-extension retirement.
P06 remains v2; other item versions, points, fixtures and the Podman pilot profile
are unchanged. P04's new runtime/notification conditions require a fresh freeze
and verified setup. Historical sittings keep their original versions and records.

This is a manual examiner checklist, not an exam runner. No step grants new
installation, isolation, model-call, message, timer or account authority.
Authoring and fixture tests do not establish candidate runtime readiness.

## 1. Resolve the launch gate before a candidate exists

Native Pi RPC subprocess control does not provide a filesystem sandbox. Normal same-user bash can read keys outside its CWD, including Git history,
other worktrees and parent artifacts. `minimal` changes discovery, not this fact.

The user approved a different launch path: whole standalone Pi in one rootless
Podman container, described in `../sandbox/README.md`. Package/setup v2 introduced
this pilot-only boundary; v3 clarified P06 staging and v4 changes nonpilot P04. Keep actual sittings blocked
until parent acceptance of its no-model preflight evidence and actual per-sitting
setup. Verify the exact image/profile, selected materials, source projection,
canary/negative visibility, credential scope and cleanup backstops. Do not weaken
the policy or fall back to a same-user native RPC child if that setup fails.
The pilot launcher does not support P04 or child model calls.

## 2. Record exact identities and permitted resources

Retain a private setup record with:

- Exam ID, package/question/key versions, Git commit, dirty-tree fingerprint and
  package fingerprint. Do not use Automata's loaded revision as the exam identity.
- Candidate exact provider/model/effort, verified effective settings, fresh-session
  identity, runtime name/version, candidate profile and operator/examiner identity.
- Automata source revision and separately each exposed asset's exact absolute
  root, source-vs-installed provenance, installed version/tree fingerprint and
  active load status. Include skills, CLI and applicable extensions. A source
  checkout is not proof of what an installed runtime has loaded.
- Candidate-visible resource allowlist: selected paper/tasks, fixtures, skill
  metadata/content, active extension docs and exposed tool contracts. Exclude
  examiner files, private checks, repository history and undeclared state.
- Task-owned read/write paths, permitted effects, time/cost/attempt limits,
  required callbacks, evidence retention and cleanup authority. Add any extra
  guidance as a separate condition; do not call it an uncoached baseline.

Supply a candidate-visible setup note with only operational facts: selected IDs,
versions/points, exact runtime/profile, absolute task roots, read/write/resource
allowlist, prepared CLI argv when P01 is selected, time/attempt budget and any
explicit P04 child approval/settings. It contains no key, expected output or
private grading checklist. The note must be fixed before timing. Native contracts
and active docs remain discoverable normally; do not preload a target skill when
its discovery is tested.

## 3. Select and stage

Knowledge paper: copy only selected question sections without changing wording,
IDs or points; retain permitted-resource instructions. Preserve an exact private
copy of what was delivered. Unselected questions are outside this run, not zeroes.

Practical tasks use separate workspaces, not the repository root:

| ID | Candidate task root and write ownership | Additional requirement |
| --- | --- | --- |
| P01 | Stage fixture contents; write selected source/installed package, backups, `out/`; preserve custom sibling | Prepared actual Automata CLI; local fixture installation explicitly allowed |
| P02 | Stage fixture contents; write `work/status.md`, `out/` only | Normal skill catalog/content; receipts read-only |
| P03 | Empty `out/`; task/resources read-only | Actual native `activity_usage`, local JSON parser |
| P04 | Stage request in approved child CWD; child writes only `work/worker-out/`; candidate writes `out/` and uses declared task-owned runtime state | Prepared standalone kernel/native-RPC profile; explicit child/notification approval and supervision |
| P05 | Stage fixture contents; write existing `work/handoff.json`, `out/` | Actual native `context_status`; fresh local process, not agent |
| P06 | Stage fixture contents; write `work/config.json`, `out/` | Python 3 stdlib exporter; other files read-only |

For P06, stage the fixture contents directly into the declared task root:
`export_report.py`, `work/` and `protected/`, plus empty `out/`. No task-root
`fixtures/` directory is required. If originals are available, the candidate setup
note must declare their exact read-only path; the Podman profile uses
`/materials/workspace/P06` for originals and `/workspace/P06` as the task root.

Create required output directories, record preservation baselines and inspect
ownership/symlinks before timing. Do not stage private expected outputs or repaired
fixtures. Check dependencies with the owning interface/help and fixture-contract
tests, never by solving the paper as a live agent. Missing dependencies stop the
setup; no shared repairs/installations are authorized by this checklist.

Profiles: `podman-pilot-standalone-v2` is the new fixed P03/P06 pilot profile.
`managed-local-subset` describes other possible subsets, not an enforced key
boundary and not the current pilot launch path.
`standalone-full-native-rpc` supports the full practical paper only with prepared
kernel/RPC controls, actual tools/permissions and the approved completion route.
Restricted subset profiles gain no child authority through shell/RPC access. A
profile change is an explicit changed condition. Readiness, actual callback/result
readback and containment must be checked in the selected profile, not inferred
from mechanical mocks or source presence. No new P04 sitting is certified here.

## 4. Freeze conditions and run only with approval

Initial pilot selection is K01/K05/K11 (6 selected / 30 full-paper points) and
P03/P06 (20 selected / 60 full-paper points). Use a fresh Terra/high session per
sitting in a fresh container/HOME with exact `openai/gpt-6.1-terra/high` checked
in actual Pi RPC state, <=15 minutes each including startup/reserved cleanup time,
one paper prompt and no retries. Follow the sandbox's explicit preflight/run
commands; no model call was made by its authoring checks. Full-paper budgets require separate explicit approval;
this package does not extrapolate them from the pilot. Parent owns launch,
supervision, reports, grading and acceptance. Author is not a candidate/examiner.

If P04 is selected after freeze, preflight its native RPC/kernel interfaces,
additional model route, one-child call budget, 120-second bound, prepared event
return and examiner fallback. Record exact resource flags and notification
permissions; no service or route is implicitly authorized. Child
output is evidence, not authority. Do not claim native cost caps not exposed by
the API. No P04 call is authorized by approval of the local-only pilot.

Do not coach, repair a sitting's environment, silently change assets, retry or
substitute a tool and then call the result unaided/comparable. Stop on mismatch.
Capture uncoached outcomes and distinguish candidate errors from invalid setup.

## 5. Capture, grade and retain

Capture bounded native/shell call receipts, return/error facts, candidate answers,
final artifacts and independent examiner checks. P03 specifically needs the real
native invocation/result plus its saved observation artifact. Compare those to
each other, not to unstable expected counters. P04 needs actual verified settings,
assignment/completion/exit facts and child-created output evidence. Preserve tool
error/unknown-outcome facts without raw private configuration or hidden reasoning.

Use separate knowledge/practical schema-v2 JSON records and Markdown reports,
linked by assessment ID. A question's `possible` is its fixed key allocation;
`earned` is null for invalid/unrun selected items. Record selected/full-paper IDs
and possible totals; a completed subset is still provisional for full coverage.
Do not list unselected IDs as failed or unrun candidate work. An unanswered item
in a completed selected sitting is zero, not `not_run`.

The result store is `.agents/var/skills/automata-agent-evaluation/runs/`, ignored
and not committed by default. Store bounded receipt/artifact copies under the same
run's private evidence location so later approved scratch cleanup cannot break
references. JSON `evidence` and `report_artifact` references point only to retained
private grader outputs, not live worker handles or deletable scratch. Do not copy
full nested transcripts, secrets or hidden reasoning. No retention cleanup is
implied by completion. Store final records atomically.

Per-question grade records include action/outcome evidence, points, call errors,
attempted-vs-completed permission effects, setup invalidations and limits. Reports
separate knowledge/practical scores, tentative mistake causes and smallest
plausible general Automata improvements. One sitting does not establish model
rankings or causation. Any post-freeze prompt/key/condition correction requires a
new package/affected-item version and appended explanation/regrade retaining the
original result. Do not silently repair a key after seeing candidate answers.
