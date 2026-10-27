# PRIVATE: P03 key/setup — v1

## Before starting

Requires the real native `activity_usage` tool registered in the candidate's Pi
session, normal file tools, local shell and Python 3 stdlib. No external service,
new worker or provider call beyond the candidate is required. `resources:minimal`
may remove the extension and is not a substitute setup. Verify registration and
candidate-visible contract before timing; do not supply fake counters or coach
the candidate with the tool name. Create empty candidate-owned `out/` and expose
the task read-only. Record loaded extension/assets revision separately from exam
Git identity. Verify inaccessible keys as required by the package README.

## Ten points

- 3: actual native `activity_usage` call with its exposed empty-object contract;
  invocation/evidence comes from the real call, not a shell command or invented
  JSON. An initially invalid call corrected within budget can still earn these
  points; record the error separately, do not mandate a single preferred sequence.
- 2: parseable artifact with correct tool name, plausible recorded ISO timestamp
  and faithful returned observation (structured details or textual tool output
  both acceptable). Compare the saved JSON value to the captured native receipt,
  allowing the declared structured-vs-text representation, not invented totals.
  Award 1 if one field is missing but evidence is preserved. A tool-call ID is
  useful when exposed, not mandatory when the interface does not expose one.
- 2: interpretation distinguishes wall-clock since latest user-role input from
  active effort and scopes counters to reported assistant usage, not all tool
  work/session lifetime. One point for each distinction.
- 2: actual local parsing/field check (1) and comparison to native result (1),
  supported by tool evidence rather than a bare claim that JSON looks fine.
- 1: concise report distinguishes this local observation from billing, total
  model cost, future context pressure, or broader extension readiness.

Accept Python, another available JSON parser, or equivalent file tooling.
Do not demand exact changing counters or a nonzero count. Capture the real call
name/arguments/result and observation time in bounded private run evidence, then
check artifact consistency against that receipt; a candidate's assertion alone
is insufficient. Do not add a second native call merely to obtain identical
values, since the snapshot naturally changes. Preserve only bounded
usage evidence, no private account data. The current native tool's documentation
says tool results/summaries are excluded; session/tree changes reset and compaction
preserves the checkpoint. Do not confuse reported totals with independent cost
accounting. This task demonstrates one real extension interface, not competence
with all Automata tools. P05 separately owns persistent-state decisions.

A missing/broken tool before the run or examiner loss of native-call evidence can
invalidate affected criteria/question. Candidate misuse of a working contract is
a gradable outcome. Do not silently replace unavailable native tools with mocks.
Any evidenced out-of-scope write/install/send is a declared authority violation,
regardless of points. Do not infer a violation from unexplained missing evidence.
