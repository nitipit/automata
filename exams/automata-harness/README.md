# Automata Harness Exams — package v4 draft / paper and key bundles v3

A diagnostic package of **12 knowledge questions (30 points)** and **six practical
tasks (60 points)**. Scores stay separate. There is no pass mark, certification or
leaderboard claim. All papers, keys and fixtures are authored; `exam.json` records
content freeze status. P04's question/key and K07's key advance to v2 for native
RPC after retirement of the legacy team extension. P06 remains v2; other item
versions, point totals and fixtures are unchanged. The new P04 profile/return route
are prospective changed conditions, not equivalent historical setups. Package v4
is a draft awaiting parent freeze; historical sittings retain their own frozen
versions. Every future sitting needs approval and verified setup.

## Owners and layout

- `blueprint.md`: package-specific coverage, difficulty, overlap and points.
- `exam.json`: stable IDs, versions, paths, points, profiles and prerequisites.
- `candidate/`: paper, practical tasks and visible fixtures only.
- `examiner/`: private keys, setup and grading notes; never candidate resources.
- General method/templates: `src/automata/skills/automata-agent-evaluation/`.

The author writes/mechanically checks; the parent examiner freezes conditions,
verifies actual setup, runs candidates and grades evidence. Software checks do not
establish exam quality or model ability. This is not a new runner/framework.

## Resource and access contract

Expose selected candidate materials, declared read-only Automata skill
metadata/content, active extension docs and exposed tool contracts. Record exact
roots and source/installed provenance, separately from the exam's Git identity.
A filtered knowledge paper preserves selected wording, IDs and points.

Writes/effects are task-specific, never general project authority. P01 explicitly
allows real installation only into its disposable fixture target/backups. P04
requires separately approved one-child work in the standalone native-RPC profile,
including its explicit completion route. Other tasks allow only their named local
file/native observation work. No shared installation/reload, production accounts,
secrets, global changes, other external messages, services or unapproved model
calls are authorized.

**Required boundaries are not implemented containment.** Native normal Pi workers
with same-user bash can read outside CWD. `inherit`, `minimal`, copies, worktrees,
instructions and ordinary same-user mode bits do not make keys inaccessible.
Git objects/history, alternate checkouts, parent artifacts and session evidence
may also expose keys. Do not supply the unrestricted repository as documentation.
Do not launch until an approved access policy has been resolved and verified.

### Bounded launch-path evidence

Native Pi RPC controls a subprocess; it does not establish a filesystem sandbox.
A task-owned kernel retains handles but does not isolate the child from the
kernel owner's environment or OS permissions. CWD/resource flags are not a
key-access boundary. The retired team extension's historical launch-path findings
remain in Git with the earlier package versions; it is no longer a setup interface.
These are interface-scope observations, not a new OS containment test or a claim
about every Pi deployment. No machine settings were changed.

The user has now approved a whole-Pi rootless Podman launch path. Its task-local
implementation and evidence contract are in `sandbox/README.md`; native RPC
subprocess control is not retroactively an isolation mechanism. Historical alternatives
for an unsupported launch path remain:

1. Postpone the pilot until an independently verified suitable execution boundary
   exposes only approved materials. A separately managed identity/host/isolation
   changes setup and needs approval; none is established here.
2. Explicitly approve an honor-bound, nonblind calibration with possible key
   exposure. It is not blinded or demonstrably uncontaminated, and is not directly
   comparable to a restricted run. The author cannot waive this condition.

Deleting keys from a copy or selecting `minimal` is not an isolation solution.
Package v2 adds only the approved pilot-specific container/launcher, not a shared
service, provider proxy, general exam runner or changed Pi worker extension.

## Profiles and pilot

- `podman-pilot-standalone-v2`: the approved new pilot setup; fresh container,
  tmpfs HOME/in-memory Pi session and exact Terra/high checks per sitting. Supports
  only P03/P06, with source-projected skills and the real activity extension.
  See `sandbox/README.md` for staging, preflight, run and exact-owned recovery.
- `managed-local-subset`: fresh normal-resource Pi worker; supports P01/P02/P03/
  P05/P06 when their dependencies are available. No P04/recursive child authority;
  shell/native-RPC access cannot bypass that profile restriction.
- `standalone-full-native-rpc`: fresh standalone Pi candidate with prepared kernel,
  native RPC and observation interfaces. Full practical use requires P04's explicit
  child/notification route, one-start/one-dispatch budget, <=120-second child bound
  and supervision. This profile is authored, not live-certified by retirement.

Record profile changes rather than silently combining unlike conditions. A full
practical paper can use one standalone profile; a nested candidate cannot be
claimed to support all six.

After the applicable package/setup freeze, parent preflight acceptance and actual setup checks, a pilot
uses a fresh **Terra/high** session per sitting with the parent's exact approved
runtime ID. Each sitting is <=15 minutes, one attempt, no retries:

| Sitting | Selected IDs | Selected/full-paper points |
| --- | --- | --- |
| Knowledge | K01, K05, K11 | 6 / 30 |
| Practical | P03, P06 | 20 / 60 |

P03 requires real native `activity_usage`, file/shell tools and a JSON parser.
P06 needs local Python 3 stdlib/file tools. Neither requires a child, network,
relay or service. Stop on a setup mismatch; never replace native output with a
mock. The full-paper time/cost budget requires separate approval, not multiplying
the pilot limit. Examiner setup details are in `examiner/setup.md`.

## Versioning and retained evidence

Package v4 retires the legacy team-extension dependency. P04 question/key v2 use a
prepared kernel/native-RPC workflow and explicitly approved event-return route;
K07 key v2 updates capability ownership without changing its question or points.
Paper/key bundle revisions advance to 3 and setup conditions to 4. This draft must
be frozen before another sitting. No old result, fixture or grade is rewritten.
The v3 package is recoverable at Git commit
`b418109a5225e7e91efd7633fd98614971ae93f0`, exam tree
`deadb4c4a292c42ad9b0ae06fb7dd3c9fe7dd3ab`.

Package v2 introduced the approved Podman setup. Package v3 clarifies that P06's
fixture contents are staged directly into the task root, with no required local
`fixtures/` directory; originals are read only at the explicitly declared path
(`/materials/workspace/P06` in the Podman profile). P06 question/key-setup versions
advance to 2; paper/key bundle revisions are therefore 2. Every other item's
question/key version, all point criteria and fixture bytes remain unchanged.

The historical v2 package fingerprint is
`031951ab16a3acf128a5ec5c9374b3e85a2026c5cc70eb92de5b21639e68d773`.
Earlier sittings retain package v2/paper-key v1; this prospective clarification
changes neither their records nor grades. Use a new material bundle and retain
the new package fingerprint before any separately approved future sitting.
Post-freeze changes to questions, keys, fixtures, points or conditions are
versioned before another run. Retain original answers/results and append any
necessary correction/regrade; do not silently tune a key after seeing work.
Record exam Git commit plus dirty-tree/package fingerprint separately from
Automata source revision and the installed assets actually loaded.

One private JSON and same-stem human-readable Markdown report per run belong in
`.agents/var/skills/automata-agent-evaluation/runs/`, already Git-ignored and not
committed by default. Use evaluation schema v2 and separate type scores, linked by
assessment ID. Record selected/full-paper IDs and points so a subset cannot
masquerade as completion. Reports contain question evidence, partial credit,
call/outcome errors, attempted/completed permission effects, setup invalidations,
tentative mistake causes and recommended general Automata improvements.

Retain bounded approved receipt/artifact copies privately with the run, not only
paths into scratch. Do not retain hidden reasoning, secrets, private account data
or full nested transcripts. Cleanup has its own authority; completion grants none.
