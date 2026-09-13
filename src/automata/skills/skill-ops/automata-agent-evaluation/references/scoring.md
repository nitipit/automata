# Evaluation Scoring

Use this reference when an evaluation needs a repeatable score or durable comparison. Keep the
agent under test separate from the evaluator that owns the rubric, evidence, and verdict. A
subject's self-report may be evidence, but it is not its own score.

## Build the Rubric

Start from observable claims and plausible failure risks for the skill or ability under test.
Write criteria that can be judged from traces, files, commands, tool results, browser evidence,
or other visible outcomes. Do not score hidden reasoning, confidence, preferred wording, or an
unstated ideal workflow.

Tag each criterion with the nearest common dimension so results can be grouped without forcing
one universal checklist:

- `activation`: recognizes when the capability applies
- `judgment`: chooses an appropriate approach
- `capability_use`: consults and uses relevant instructions, examples, and tools
- `outcome`: produces the intended correct and useful result
- `boundaries`: respects scope, permissions, safety, and ownership
- `recovery`: responds appropriately to ambiguity, missing prerequisites, or failure

Use only applicable dimensions. Ability-specific criteria define what is actually measured.
Record `not_applicable` criteria when their absence matters for interpretation, but exclude them
from the earned and maximum totals.

## Score Observable Criteria

Use the same three-point scale for each applicable criterion:

- `0`: absent, incorrect, unsupported, or harmful
- `1`: partially correct, inconsistent, or successful only after evaluator repair
- `2`: correct without repair and supported by direct evidence

Every score includes concise evidence that establishes the observed behavior. Keep exact excerpts
or stable artifact references when useful, but do not retain raw transcripts merely to justify a
number.

A rubric declares:

- its stable ID and version;
- scenario IDs and versions;
- each criterion, dimension, expectation, and maximum score;
- any criterion-specific minimum;
- critical gates; and
- its passing threshold, defaulting to 80 percent when no stronger domain threshold is justified.

Do not silently revise a rubric after seeing a result. Version a material criterion, gate,
scenario, or threshold change before using it in another run.

## Critical Gates and Verdict

Keep critical gates separate from numeric scores so a high average cannot hide a required safety
or correctness failure. A gate has an expected observable condition, `PASS` or `FAIL`, and bounded
evidence.

A run is `PASS` only when all of these are true:

- no critical gate failed;
- the score meets the rubric threshold; and
- every criterion-specific minimum is met.

A run is `FAIL` when observable subject behavior causes a gate, threshold, or required criterion
to fail. Classify the cause as a behavior or activation failure when supported by evidence.

Use `INCONCLUSIVE` when a valid run cannot distinguish among plausible outcomes. A harness or
environment failure is not an agent-ability score: report and classify it, but do not add it to
scored ability history. Do not silently retry it; another run requires remaining approved budget
and a justified recovery decision.

## Compare Repeated Runs

One fresh run is a smoke test. When repeatability matters, retain each independent run and report:

- passed runs over valid scored runs;
- arithmetic mean percentage;
- minimum percentage; and
- critical-failure count.

Do not report only an average. Compare or aggregate runs only when subject revision, rubric,
scenario, runtime, model and effort, permissions, and relevant environment are compatible. When
one of those conditions changes, show a separate cohort rather than implying a direct ability
trend.

## Retain Scored Results

When scored evaluation and result retention are part of the accepted evaluation contract, save
one valid JSON record per completed `PASS`, `FAIL`, or genuine `INCONCLUSIVE` run. In an Automata
repository without a more specific convention, use:

```text
.agents/var/skills/automata-agent-evaluation/runs/
```

Use a sortable filename such as:

```text
YYYYMMDDTHHMMSSZ-<subject>-<run-id>.json
```

Start from `../templates/evaluation-record.json`. Keep `schema_version`, rubric version, scenario
version, subject revision, runtime identity, and scoring conditions explicit. Record bounded
inline evidence or references to approved durable artifacts; do not leave references that point
only to deleted temporary files.

Keep raw traces, disposable workspaces, browser profiles, timers, and background processes out of
the retained record and clean them up after extracting evidence. Never retain secrets, private
account data, hidden reasoning, encrypted reasoning, or full transcripts in evaluation history.

Store each run atomically as its own file. Do not maintain one growing JSON array. JSON is the
initial source of truth; a database or spreadsheet may later import these records without changing
the run contract.
