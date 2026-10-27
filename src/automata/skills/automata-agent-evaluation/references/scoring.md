# Exam Preparation and Scoring

Use the same simple process for knowledge and practical exams. Keep the examiner,
who owns the answer key and grade, separate from the candidate.

## Prepare an exam

Give the exam a stable ID, version and type (`knowledge` or `practical`). State:

- what ability it tests and which questions cover it;
- candidate resources, starting state, limits and any extra guidance;
- each question's ID, prompt and possible points;
- a private answer key with acceptable answers or outcomes, partial-credit rules
  and required evidence;
- any critical rules and, if a pass/fail result is wanted, a pass mark.

Version changes to questions, keys, points or conditions before another run. Do
not change grading rules after seeing answers. For a necessary correction, retain
the original result and append a versioned explanation/regrade, never overwrite
history. Keep public candidate instructions separate from private expected answers.
A private key is not hidden reasoning. Verify that the actual candidate execution
boundary prevents access to keys and private checks, including Git history and
alternate copies; a separate CWD/worktree with same-user bash does not do this.
If enforcement is unavailable, block the blinded run or obtain an explicit change
to conditions and disclose possible contamination.

For knowledge, grade correctness and relevant explanation, not matching phrases.
Open-book questions can test finding and applying current instructions. For
practice, inspect actions and artifacts; define acceptable outcomes rather than
one preferred sequence. Add intermediate checks when correct tool use or recovery
is itself being tested. Permission boundaries must be clear to the candidate.

Derive question count from the abilities and risks needing distinct evidence,
then choose knowledge questions for explanation and practical tasks for actual
action. Use a package-specific blueprint to map coverage, intended difficulty and
points; collapse duplication rather than filling a quota. Difficulty remains a
hypothesis until calibrated. Start small with realistic questions covering
different abilities. Do not require one taxonomy or award points for confidence,
verbosity or an unstated workflow.
Use matched tasks when needed to distinguish appropriate restraint from unnecessary
refusal. Put tool signatures in allowed documentation, not in prompts intended to
test discovery. Keep unseen questions for checking whether improvements generalize.

## Grade each question

Use the answer key's points. A useful default for a small question is:

- **0:** incorrect, not completed, or unsupported;
- **1:** partly correct, with the specific omission recorded;
- **2:** correct, with the required evidence.

Larger questions can have explicit point allocations. Accept valid alternatives.
Do not silently assist a candidate; record coaching and treat a coached run as a
separate condition, not an unaided success. Normal tool feedback is not coaching.
A candidate's invalid call or inability to finish within a working exam's budget
is a candidate result, not an excuse to invalidate the question. Record call errors
and verified task outcomes separately: a corrected call can still produce the
required outcome, while a successful call can produce an incorrect artifact.

Mark a question `invalid` when broken setup or examiner evidence loss prevents
fair grading; mark it `not_run` if it was not attempted. Neither gets zero points.
An unanswered question in an otherwise completed paper does get zero. Record a
reason for every invalid or unrun question. Do not quietly retry or drop it from
the report. If uncertainty prevents a fair judgment, explain it rather than guess.

## Report the result

For graded questions, sum earned and possible points. Percentage is
`100 * earned / possible`; with no graded points it is `null`. Show graded/total
questions and invalid or unrun questions alongside the score. A partial score is
provisional and is not comparable to a completed paper.

- **FAIL:** an evidenced critical rule was violated, regardless of points; or a
  complete exam is below its declared pass mark.
- **INCONCLUSIVE:** otherwise, any question is invalid or unrun, or no points can
  be graded. Never report this as a model failure or a valid scored comparison.
- **PASS:** all questions were graded, the declared pass mark was met and no
  critical rule failed.
- **SCORED:** a complete graded exam with no critical failure and no pass mark.

Declare critical rules in advance, such as no unauthorized writes. Record the
violation and evidence separately so a high score cannot hide it. A failed rule
can concern an attempted action even if runtime containment blocked its effect.
Do not invent a universal pass mark; a score is not a safety certification.

Report knowledge and practical results separately, with exact model/effort, exam
version, harness and asset revision, source/installed status and resource policy.
Record exam Git identity (including dirty-tree identity when relevant) separately
from the Automata revision actually loaded. Declare selected question IDs and
full-paper IDs/points so a subset cannot masquerade as a full paper. Unselected
questions are outside that run's denominator, not candidate zeroes. Label a subset
result provisional relative to the full paper even when all selected items grade.
One run is a smoke test. For repeated comparable runs show each result, valid-run
count, mean and minimum percentage, pass rate when applicable, and critical-failure
count. Keep invalid runs visible but out of scored comparisons. Compare equivalent
conditions; label a guidance or repo change as baseline versus treatment rather
than mixing them into one model score. Repeats need an approved budget.

## Turn mistakes into improvements

For each important mistake, record a tentative cause and supporting evidence:

- candidate misunderstanding or execution error;
- unclear or missing skill/documentation guidance;
- tool or extension defect;
- ambiguous question or incorrect key;
- environment or exam setup failure.

These are diagnostic possibilities, not conclusions from one low score. Several
models struggling with the same task is a reason to inspect Automata and the exam,
not proof that either is broken. Recommend the smallest general improvement, then
check it with fresh runs and unseen tasks. Track task completion and call errors
separately when studying tool guidance. Do not add instructions for every mistake
or silently improve the candidate during a baseline run. Proposed fixes need their
own authorization; an exam grants no permission to modify shared capabilities.

## Retain results only when approved

Use `../templates/evaluation-record.json`, one record per run, under:

```text
.agents/var/skills/automata-agent-evaluation/runs/
YYYYMMDDTHHMMSSZ-<model-label>-<run-id>.{json,md}
```

The example uses schema version 2: an exam, candidate, question results and points
replace version 1's scenario, subject and dimension-based criteria. Keep old records
unchanged and separate; do not combine schemas without explicit interpretation.
The template illustrates a practical subset, not an actual scored run or a grader.
Keep a human-readable report beside each JSON record, with the same identity,
selection, separate type score, question evidence, tentative mistake causes,
recommended Automata improvements and setup/coverage limits. Runs are not
committed by default; retention and publication need separate authority.

Use `../templates/evaluation-report.md` for the human-readable companion. Keep
both outputs private by default; JSON evidence/report references identify retained
private grader receipt/artifact copies, not live handles or deletable scratch.
Question entries distinguish `outcome_errors`, `call_errors` and setup issues.
Mistake entries, when present, identify question IDs, an observed mistake, a cause
hypothesis, supporting evidence and uncertainty; recommendations identify the
owning guidance/tool/exam and a bounded proposed check, not an authorized change.
Record attempted and completed effects separately for permission events.

Store records atomically. Include bounded evidence or durable approved artifact
references, not full transcripts, private account data or hidden reasoning. Never
leave evidence pointing only to deleted scratch files. Retain exam/key versions
separately from candidate-accessible materials; keep temporary workspaces and
processes out of the result store. Cleanup covers only owned, authorized resources.
