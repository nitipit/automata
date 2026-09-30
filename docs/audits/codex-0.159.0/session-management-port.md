# CX-007: scoped native session copy and recoverable removal

Extends the accepted CX-006 assets without changing Pi runtime behavior, activating
anything globally, or adding a chat launcher, daemon attachment, MCP adapter or
custom Codex binary. The shared catalog gains `automata-codex-sessions` (41 skills;
all previous 40 remain). Historical earlier audit counts remain historical.

## Native facts and independent-copy boundary

Pinned native runtime: Codex 0.159.0; public source commit
`687a119f0fcaace47e1f1abcc77cec6c813fd6da`. Relevant boundaries under `codex-rs/`:
`app-server-protocol/src/protocol/v2/thread.rs`,
`app-server/src/request_processors/thread_processor.rs`,
`app-server/src/request_processors/thread_delete.rs`, and
`core/src/thread_manager.rs`. Executable fixture evidence, not interface names,
establishes the delivered contract:

- Native `thread/fork` creates a fresh ID but can retain `history_base` references.
  That operation is exposed as **linked fork**, never claimed as independent copy.
- Moving only a JSONL back after native deletion is insufficient: the thread/history
  projections must be rebuilt. Targeted `thread/resume` with the original path
  rebuilt a usable native history and preserved original turn/item identities.
- A selected standalone paginated rollout can be copied byte-identically into a
  private store. Native resume/fork generates a fresh destination header. The
  adapter removes its reference backing (`history_base` and cutoff), resets its
  ordinal to zero, and appends the exact original record tail. It rewrites neither
  source history nor historical content/paths. A separate empty store containing
  only this child must successfully resume it with the same canonical full-turn
  digest before the destination is published in the selected store.
- The independent result retains native source provenance (`forked_from_id`) but
  has no history dependency. Provenance alone is not an effect-closure edge. A
  linked source requiring unresolved ancestral history is unsupported for copying.

The exploratory legacy-import approach was rejected: it lost native item
projections. It is not retained as an alternate production mechanism. No plain
file-copy or linked-fork fallback is offered when independent verification fails.

## Authority and supported envelope

`session_management.py` supports `list`, `copy`, `fork`, `trash`, `restore` through
explicit absolute native-store and management-state roots. There is no default
global store, filesystem conversation search or implicit cross-project scope.
Listing uses pinned native index columns and indexed rollout headers; it excludes
previews and message bodies from results/state. Scope is exact cwd or explicitly
all projects in the selected store, capped at 10,000 rows, page size1–100/default20.
Missing roots, unindexed coverage, unavailable entries and missing project
folders are reported; none authorizes removal.

Private five-minute receipts bind store device/inode, caller, page IDs and selected
row/file snapshots. Separate action receipts are one-use; newer pages/listings
supersede them. Source checks run again around native effects. Known current IDs
are excluded; conflicting current identity is rejected. Mutations require exact
IDs, an explicit trusted pinned binary and `--inactive-owned`; a truly external
caller can attest `--outside-session`. These flags do not detect other processes.
The namespace lock coordinates this helper/state root, not all native writers.
Inactivity and user authorization remain prerequisites, not inferred from age.

Copy targets an existing different cwd within the same native store. No project
files, external assets, operational state or historical paths are transplanted.
Copy/trash accept only materialized paginated histories; archived, pinned,
project/section/agent-enriched state and unsupported goals, queues, memories,
dynamic tools or attachments are rejected rather than partially preserved.

Before any native removal, `effect_closure` inspects all indexed headers and spawn
edges **inside the explicitly selected store**, including outside the discovery
cwd. It rejects unselected descendants/history dependents; even entirely selected
dependency groups remain unsupported. Malformed/unknown dependency metadata or
unrelated incompatible rows can conservatively block the action. This broad
metadata inspection is for safety, not authority to mutate those other sessions.

`session_native.py` requires Linux bubblewrap. Short-lived app-server stdio runs
with a private network, synthesized HOME/config/provider, disabled hooks, goals,
plugins, memories and background migration. Existing credential/config surfaces
are masked; ordinary project contents are not mounted. Logical CODEX_HOME paths
remain stable while the explicitly selected SQLite backing store is bound.
There is no unsandboxed fallback or model-turn method. Absolute request/receive
deadlines apply even to buffered or continuously ready notifications; process-free
tests exercise those cases. This is management transport, not a persistent host.

## Recovery ordering and failure contracts

1. Validate every selected ID and the selected-store dependency/effect closure.
2. Read native complete turns and persist SHA256 of canonical JSON plus turn/item
   counts. Every field is included: user/assistant/tool payloads, IDs and times;
   there are currently **no volatile-field exclusions**. No extra raw native-turn
   text is saved in the signature or journal.
3. Stage only selected original rollouts and their recovery metadata/hashes;
   fsync files/manifest/directories. Never copy whole unrelated SQLite stores.
4. Use actual `gio trash`, verify the package and freedesktop `.trashinfo` including
   the original staging path and deletion timestamp, then mark recovery prepared.
   Staging and the explicitly authorized XDG trash must share a filesystem.
5. Only then call native delete for exact selected roots. Recheck remaining IDs
   between batch steps. Parent selection is never child authority.
6. Restore only exact recorded IDs to original receipt-bound paths; refuse native
   row/path collisions and tampered/missing recovery data. Create files exclusively
   with mode0600, run targeted native resume to rebuild projections, restore name,
   and verify original identity, complete native history digest and original raw
   rollout prefix. Resume may append native settings; the original bytes must
   remain an identical prefix. A JSONL-presence check alone cannot pass restoration.

Per-ID results distinguish succeeded, failed and unattempted. Partial/unknown
outcomes stop the batch, preserve recovery artifacts and warn against automatic
retry. Failed independent-copy verification before publication creates no public
destination; failure after publication leaves the destination intact and reports
its ID/potential presence. No automatic destination deletion or permanent-delete
fallback occurs. Temporary private copy-validation stores are internal disposable
work, not user destinations.

Receipts, copy provenance and recovery journals stay in private capability-owned
state outside native store/replaceable assets. Genuine trash bundles contain the
selected original history and remain after restoration. No automatic retention
purge is provided; owner review must account for pending recovery and partial
outcomes. Native operational logs/caches, arbitrary external assets and complete
runtime configuration are not part of the restore contract.

## Executable evidence

```sh
python tests/integration/automata/codex_runtime/session_management_probe.py \
  --binary "$NATIVE_CODEX_01590" --state-root "$NEW_OWNED_FIXTURE_ROOT"
python tests/integration/automata/codex_runtime/verify_session_management_probe.py \
  "$NEW_OWNED_FIXTURE_ROOT"
```

The existing isolated sequence harness supplies fresh HOME/CODEX_HOME, generated
project/history, private network and loopback mock provider. Only fixture creation
uses four mock requests: two turns with meaningful user content, successful native
command execution (command/stdout/exit0), and assistant content. Management adds
**zero** requests, never calls a real provider, and reads no real histories,
credentials or config. The helper itself also isolates its management subprocesses.

Fresh evidence: sibling `test-state/session-final-1`; manager independently reran
`test-state/session-manager-1` and its verifier successfully. Earlier targeted
recovery/source-free-copy experiments remain in sibling task evidence directories.
The final installed helper proves:

- metadata listing/receipts, explicitly labelled linked fork, and pre-effect
  rejection of a parent with an unselected history-dependent fork;
- genuine OS-trash package and metadata before native removal, original UUID/name
  restored, exact full native turn/item payload equality, valid native DB/paths;
- independent copy with fresh identity, destination cwd, original source provenance
  and identical full history, source bytes unchanged;
- child alone in a third store, no source row/file, still resumes with equal digest;
- both an unselected original and its linked fork preserve **complete `threads`
  rows, full native turns and rollout-byte digests** across the later operations.
  This is selected known-row/history invariance, not a claim that operational
  logs or every SQLite byte are unchanged.

## Regression results

```sh
PI_TEST_PACKAGE_ROOT="$INSTALLED_PI_0991" \
PI_SKILL_ACTIVITY_SDK="$INSTALLED_PI_0991/dist/index.js" \
PI_SESSIONS_NATIVE_SDK="$INSTALLED_PI_0991/dist/index.js" \
uv run --offline --with shelfdb==3.0.2 --with dictify==5.0.2 pytest \
  tests/unit/automata/plugin tests/cli/automata/cli_test.py \
  tests/cli/automata/codex_test.py tests/unit/automata/install/skills_test.py \
  tests/unit/automata/install/pi_extensions_test.py \
  tests/integration/automata/extensions/token_awareness_test.py \
  tests/integration/automata/extensions/message_timestamps_test.py \
  tests/integration/automata/codex_runtime/token_awareness_test.py \
  tests/integration/automata/codex_runtime/context_awareness_test.py \
  tests/integration/automata/codex_runtime/skill_activity_test.py \
  tests/integration/automata/extensions/skill_activity_test.py \
  tests/integration/automata/extensions/pi_sessions_test.py \
  tests/integration/automata/codex_runtime/session_management_test.py \
  tests/integration/automata/codex_runtime/session_native_test.py -q
```

**174 passed, no skips**: prior134, two Pi sessions checks (including actual isolated
native Pi SDK), and38 new Codex safety checks. These cover receipts/scope/staleness,
current/inactivity boundaries, paths/symlinks, missing roots/cwds, dependency and
ancillary rejection, complete-content digest changes, real OS-trash/tamper/collision,
partial removal and failed-copy publication, native deadlines and startup cleanup.

The new shared skill intentionally changes current catalog invariants40→41 while
preserving both Pi/Codex session guidance. An additional **73 passed** across
`tests/integration/automata/{skills,package}_test.py` and
`tests/apps/skill_builder/{test_build,test_browser,test_catalog_browser}.py`, using
cached offline FastAPI/httpx/Jinja/watchfiles/Mistune dependencies. This includes
wheel/sdist installation and isolated browser catalog checks, not user-profile
access. One third-party Starlette/httpx deprecation warning; no failures.

The native proofs establish mechanism/content preservation, not live-agent
judgment, other-process liveness, arbitrary ancillary-state recovery, other runtime
versions or blanket Pi parity. No global installation/activation, real-model trial,
merge, push or next capability is included.
