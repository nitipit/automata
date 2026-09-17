# Testing an agent system

Automata combines executable software, instruction packages, and an agent acting
in an environment. They need different evidence. A green pytest run is not a
claim that the agent has good judgment; a persuasive agent answer is not proof
that the software works.

## Match the check to the claim

| Claim | Useful evidence | Does not establish it |
| --- | --- | --- |
| Router authorization, correlation, lifecycle, installer behavior | Unit/CLI/integration tests against the relevant executable boundary | A sentence promising safety |
| Skill can be discovered and installed | Frontmatter, unique names, file/tool references, exact installed files | Counting mentions of a capability |
| Agent recognizes a need, chooses an approach, respects authority | A realistic task with observed actions, results, and evaluator judgment | Required phrases, headings, word counts, or subject self-report |
| Browser interaction works for a person | Visible target changes, usable controls, correct replies, recovery evidence | HTTP 200, injected input, or a successful transport acknowledgment |
| A change improves behavior | Comparable baseline/candidate runs on relevant scenarios | One successful demonstration, especially after repairing it |

Nondeterministic does not mean untestable. An unauthorized deletion attempt is a
failure even if an OS guard blocks it. Several different plans or explanations
may all be good; judge their consequences and evidence, not a golden sentence.

## Deterministic suite

- `unit/`: direct code and policy behavior.
- `cli/`: command interfaces.
- `integration/`: installation/package contracts and external runtime boundaries.
- `behavior/`: whole-agent scenarios and evaluation guidance, separate from pytest.

Keep existing software tests where they are; this separation does not require a
new framework or moving working tests. Commit reusable scenarios and safe fixtures,
not private run evidence.

Run from a clean checkout:

```sh
uv run --offline pytest -q
uv run --offline ruff check src tests
```

Some integration checks require installed runtimes and cached dependencies. Report
skips and the boundaries replaced by stubs. For the opt-in native Pi SDK tests,
set `AGENT_BROWSER_BRIDGE_NATIVE_PI_PACKAGE` to the installed Pi package directory.
Those tests use a local model stub, not a real model. The legacy environment-variable
name is retained by that test harness.

Skill-package checks validate parsable metadata, catalog identity, actual declared
assets/tool paths, and installation contents. They deliberately do not assert
specific prose, exact activation descriptions, section names, size limits, or a
fixed order of advice. A reference check proves that an asset exists, not that its
advice is correct. Existing source/export inspections elsewhere are similarly
structural evidence, not execution of the behavior they mention.

Assertions on program output can be appropriate when that output is the public
contract. This is different from asserting that instruction prose contains words
which supposedly guarantee future behavior. Do not replace prose assertions with
more elaborate regexes or an LLM that merely checks for the same phrases.

## Instruction review and behavioral evaluation

For an instruction change, first review the actual semantic delta: intended
capability, activation and nearby non-activation situations, authority, ownership,
conflicts, and a useful outcome. Check whether the instruction belongs in a skill,
a runtime mechanism, character, or temporary task context. A rename or typo fix
usually needs structural checks and semantic review—not paid agent experiments.

When activation, judgment, safety, recovery, or user-visible behavior changes,
select relevant [behavioral scenarios](behavior/README.md). Do not run every skill
or launch a team as a ceremony. Follow the existing
[agent-evaluation guidance](../src/automata/skills/skill-ops/automata-agent-evaluation/SKILL.md)
for authorization, isolation, runtime verification, budget, and cleanup.

1. Freeze the claim, fixture, natural task, allowed effects, failure conditions and
   evidence before the run. Keep evaluator expectations out of subject context.
2. Use a fresh subject with normal discovery of its intended instructions/tools.
   Do not secretly prevent skill reading and then score activation failure.
3. Observe tool calls and side effects, canonical receipts, artifacts, UI results,
   and the user's meaningful outcome. Record facts separately from interpretation.
4. Judge with an explicit rubric. Objective invariants can be checked by code;
   usefulness and tradeoffs need reasoned review. An independent human or agent
   evaluator can help, but its conclusion must cite evidence. Do not score hidden
   reasoning or let the subject certify its own work.
5. Classify failures before changing anything: behavior, activation, harness,
   environment, or genuinely inconclusive. Never repair the subject in a run and
   relabel that same run as a pass. Preserve the failed attempt and rerun only
   within authorized budget.

For consequential comparisons, use matched conditions: subject revisions,
scenario/fixture version, runtime, model/effort, tools, permissions and relevant
state. Keep sessions independent, include a nearby or adverse variant, and repeat
when the decision warrants it. Report failures and variation, not only the best
run. A prompt learned from the expected answer is not independent validation.
A successful run without the skill is not evidence that the skill caused success.

## Reporting and acceptance

Report these separately:

- **Software/package:** command, result, skips and real vs stubbed boundaries.
- **Instruction review:** semantic changes and unresolved concerns.
- **Agent behavior:** scenarios actually run, runtime, observed outcome, failure
  classification and limits. Use `PASS`, `FAIL`, or `INCONCLUSIVE` for executed
  claims; `NOT RUN` is a coverage status, not a scored evaluation result.
- **User workflow:** what was visibly usable, what required intervention, and any
  gaps between a scripted smoke test and ordinary use.

A safety/authority failure cannot be averaged away by successful easy cases.
Numerical scores are optional and scenario-specific, not a universal agent-quality
percentage. For scored comparisons, reuse the existing evaluation record/scoring
format rather than introducing another database or runner. Keep secrets, raw
transcripts and hidden reasoning out of reports. Distinguish uncached input,
output and cached reads when reporting model use.

Acceptance is proportional to risk and the actual claim. Missing live evidence
must remain visible as a limitation, an explicit accepted risk, or a blocker for a
claim that depends on it—not be converted into "verified" by a larger test count.
Do not require live runs for unrelated deterministic changes.

## Revision of the old suite

The former per-skill phrase tests and prose checks in `skills_test.py` are retired.
Review of the twelve retired per-skill modules found prose assertions mixed with
catalog, mapping, asset and independent-installation checks. The useful mechanical
checks are consolidated in `integration/automata/skills_test.py`, including required
skill names, exact tool mappings, referenced assets and selected-skill installation.
Checks on exact descriptions, advice order, size caps and presence of particular
sentences were not retained as behavioral evidence. Software/runtime tests remain
unchanged. Four starter scenarios in `behavior/` address useful results, judgment,
authority and reliable completion; they are not one-for-one replacements for the
removed assertions. This removes false proxies; it does **not** mean those scenarios
have passed or that behavioral coverage is exhaustive. Add a concrete regression scenario when a real failure
reveals a missing boundary, rather than freezing the corrective sentence in pytest.
