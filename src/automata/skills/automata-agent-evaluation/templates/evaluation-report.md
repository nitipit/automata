# Evaluation report: <run-id> — <knowledge OR practical>

Template only; not an actual run. Keep this report and its schema-v2 JSON companion
in the approved private run store. References below point to retained private
grader evidence copies, not candidate-accessible keys or deletable scratch.

## Identity and conditions

- Assessment/run ID and date: <linked assessment, unique run, ISO timestamp>
- Exam: <ID, package/question/key versions, Git commit, dirty/package fingerprint>
- Candidate: <exact provider/model/effort, verified fresh session, launch profile>
- Runtime/assets: <harness/version; Automata source revision; actual source or
  installed skill/CLI/extension roots, versions/fingerprints and load status>
- Examiner: <identity/model/effort if applicable; not the candidate>
- Resources/authority: <read/write/effect boundaries, added guidance, key-access
  verification or explicitly approved nonblind condition>
- Budget: <time/cost/attempts; actual use, interruptions; no hidden retries>
- JSON record: <retained-private-run-record.json>

## Coverage and score

- Type: <knowledge OR practical; do not combine their scores>
- Selected IDs / selected possible points: <...>
- Full-paper IDs / full-paper possible points: <...>
- Graded / selected questions: <...>; invalid / not run: <IDs and reasons>
- Earned / graded possible points / percent: <...; null when none graded>
- Result: <SCORED/PASS/FAIL/INCONCLUSIVE under the declared rules>
- Coverage: <full or subset; subset remains provisional for full-paper ability>
- Critical rules: <declared rules and separately evidenced violations, if any>

## Question evidence and partial credit

| ID/version | Status | Earned/possible | Observed action/outcome and private evidence | Omission/limits |
| --- | --- | --- | --- | --- |
| <ID> | <graded/invalid/not_run> | <points or null> | <bounded receipt/artifact reference> | <key-based reason> |

Distinguish call errors from outcome errors and setup invalidations. Record
attempted permission violations separately from completed effects; do not infer
unobserved effects. Valid alternative approaches earn the same outcome credit.

## Mistakes and tentative explanations

For each important observed mistake: question ID, the observation, supporting
private evidence, plausible cause(s), uncertainty and competing explanations.
Separate candidate misunderstanding/execution from guidance gaps, tool defects,
question/key ambiguity and setup failure. No confidence or hidden-reasoning grade.

## Recommended Automata improvements

For each recommendation: the evidenced problem, owning skill/tool/runtime/exam,
smallest general change to consider, and a bounded fresh/unseen verification.
Recommendations do not authorize implementation or establish causation from a
single run. Preserve original results if later correcting a versioned key.

## Limits, retention and next action

State exposure/contamination, profile changes, missing evidence, partial coverage,
invalid setup and untested capabilities. Identify retained private evidence,
remaining owned resources and cleanup authority; completion is not permission to
delete. End with the next decision/check, not a claim of general certification.
