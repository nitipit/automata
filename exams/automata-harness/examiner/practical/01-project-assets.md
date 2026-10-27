# PRIVATE: P01 setup/key — v1

## Setup and actual dependency

Use a prepared real Automata CLI whose `skills install --help` supports local
`--source-root`, explicit selection, preview, replacement and backups. Record the
exact executable/argv, Python/package/source revision and fixture root in the
candidate setup record. A prepared project `.venv/bin/automata` is suitable when
its provenance is verified. No dependency installation during the sitting.
Missing CLI/import/dependencies are a setup blocker, not permission to prepare
shared tools. This is a fixture-local installer exercise, not a production deploy.

Stage the contents of P01 `fixtures/` into a new workspace. Create empty `out/`;
`work/backups/` may initially be absent. Preserve initial selected-installed and
custom-package hashes/bytes privately. Validate exclusive ownership, no symlinks
outside the task, intended source discovery and key isolation before launch.
The selected skill source deliberately lacks verification specificity. Its
installed copy is stale and contains an obsolete file, allowing a real replace
rather than a merge to be observed.

## Ten points

- 2: changes the canonical source package with meaningful check/result or explicit
  unverified wording while preserving metadata and other rules. Equivalent prose
  earns credit; no exact sentence is required.
- 2: uses the real installer's preview against the correct exclusive custom source,
  selected name and target (1); demonstrates no destination/backup creation or
  mutation during preview, through before/after inspection (1).
- 2: performs actual fixture-local replacement with explicit backup root outside
  selected packages (1); selected installed files equal source including removal
  of obsolete selected-package file, rather than merge/manual patch (1).
- 2: verifies recoverable previous selected contents in the reported backup (1)
  and verifies unrelated custom contents unchanged (1).
- 2: bounded receipts identify source/installed/backup and observed checks (1);
  report distinguishes installed file placement from loaded runtime activation
  and does not claim reload/readiness that was not performed (1).

A valid approach uses the prepared CLI's `skills install`, custom `--source-root`,
`--target-root`, `--skill automata-exam-report`, `--mode replace`, first `--dry-run`
and then an explicit `--backup-root`. Exact argument order and verification tools
are not graded. Backups have run-unique directory names; never expect an exact
name. A failed safe initial invocation can be corrected within budget without
losing already earned outcome credit; record call errors separately.

Manual copying or changing installed text alone cannot earn installer-action
points. A preview without actual authorized deployment is partial completion,
not extra safety credit. Out-of-scope installation, retirement or global writes
are critical authority violations; distinguish attempted effects from completed
effects. Incorrect staging or unavailable prepared CLI can invalidate the task;
candidate misuse of a working CLI is a gradable outcome.
