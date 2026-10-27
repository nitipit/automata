---
name: automata-agent-evaluation
description: Use for preparing, running and grading knowledge or practical exams for agents, and using results to improve agent guidance and tools. Not for ordinary software tests or prose review.
---

# Automata Agent Evaluation

Give an agent an exam, grade observable evidence against a separate answer key,
and use the mistakes to improve the harness or choose suitable models. A score
measures performance on that exam, not general intelligence or safety.

## Two exam types

- **Knowledge:** grade answers about concepts, rules, interfaces or approaches.
  State whether documentation and read-only tools are allowed; default to open-book
  for harness knowledge. Correctly finding and explaining current guidance matters
  more than memorizing it. Troubleshooting can be a written question.
- **Practical:** grade work done with skills, tools and extensions in a controlled
  workspace. Check calls, artifacts and outcomes, not just the candidate's report.
  Troubleshooting can be part of the task. Do not reward inactivity when useful
  action is authorized, or treat a blocked unauthorized attempt as sound judgment.

Keep their scores separate. Use one exam type per run; a combined assessment has
one result for each type. Keep reusable exams and answer keys outside this skill.

## Prepare, run, grade, improve

1. **Prepare the paper and key.** Define the ability being tested, realistic
   questions or tasks, allowed resources, points and acceptable evidence. Keep the
   answer key and grading notes out of the candidate's session and accessible files.
   Verify that separation is enforced by the execution boundary, not just a CWD
   or an instruction; otherwise stop or explicitly revise the exam conditions.
   Accept valid alternative approaches; require an exact tool only when its use is
   the ability under test. Read `references/scoring.md` before setting points.

2. **Agree on conditions.** Confirm the exact model/effort, harness and asset
   revision (installed or source), permissions, time/cost budget, repeats, evidence
   retention and cleanup authority. Record additional guidance as a separate exam
   condition. Use disposable workspaces for practical changes, no secrets or live
   accounts. Real-project writes and extra effects need explicit authority.

3. **Run without coaching.** Use fresh sessions and normal discovery within the
   declared resources. Do not name a skill when testing whether it is discovered.
   Verify the actual runtime, assets and isolation before starting; stop on a setup
   mismatch. Do not repair or coach a candidate mid-run and call it an unaided pass.
   For asynchronous exams establish an owner, reachable callback and bounded fallback
   wake before launch; yield while waiting. A log or timeout is not a wake-up path.
   Every attempt counts toward the budget; no silent retries.

4. **Grade and report.** Grade answers for knowledge, actions and verified outcomes
   for practice. The candidate does not grade itself. Record question-level points,
   concise evidence, critical failures and limits. Broken setup or missing evidence
   is not automatically a candidate failure. Report incomplete results as provisional.
   Use `templates/evaluation-record.json` and `templates/evaluation-report.md` when
   result retention is approved; declare subset IDs and keep exam identity separate
   from loaded asset identity. Do not retain hidden reasoning, secrets or full
   nested transcripts. Cancel obsolete wake triggers and clean up only owned
   resources within the agreed authority.

5. **Use mistakes to improve.** Distinguish candidate errors from unclear guidance,
   tool defects, bad questions and environment failures before proposing changes.
   Prefer general fixes over instructions tailored to an answer key. Compare fresh
   baseline and revised runs, including unseen tasks, within an approved budget.
   Report evidence and uncertainty, not just a total. Results guide improvements;
   they do not authorize repo changes, installs, pushes or permission grants.
