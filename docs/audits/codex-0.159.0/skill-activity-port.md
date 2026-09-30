# CX-006: automatic native skill insertion recording and query

Extends CX-004/CX-005 without changing Pi or deploying a custom Codex host,
launcher, binary, daemon or MCP server. Production uses ordinary supported hooks
plus explicit session-scoped shell controls. Shared skills remain one catalog.

## Evidence selected, not inferred

Pinned public source `687a119f0fcaace47e1f1abcc77cec6c813fd6da`, under `codex-rs/`:

- `ext/skills/src/host_prompt.rs`, `HostSkillsSnapshot::load_skill_prompts`: only
  successful native skill reads produce instruction fragments; errors produce
  warnings instead. Plugin instructions may be natively truncated.
- `ext/skills/src/fragments.rs`, `SkillInstructions`: native content kind is
  `skills.selected_skill_instructions`; wrapper supplies name/path. This differs
  from available-skill catalogs and ordinary `user.text`.
- `core/src/session/turn.rs`, `build_skills_and_plugins` and insertion loop:
  generated instruction items enter the conversation via
  `record_conversation_items`. The real 0.159.0 fixture persists their native
  message ID, turn ID, per-part content kind and original log timestamp.
- `core/src/skills.rs` and `skills/src/invocation.rs`: implicit shell invocation
  analytics recognize command intent, not a successful complete read. They are
  deliberately not used as activation evidence here.

`skill_records.py` recognizes only metadata-tagged local-file instruction
insertions, not wrapper-shaped user text, catalogs, mentions, shell reads/scripts
or cooperative reports. It extracts identity from the insertion itself and reads
no skill files. Resource-backed/non-local skill metadata is unsupported and fails
coverage closed. Records use `runtime: codex` and
`evidenceKind: native_instruction_insertion`: this is not Pi's complete-read
contract, proof of compliance, all native invocation kinds or current context
presence. Partial native instruction insertion can still count as insertion.

## Implementation and storage

`token_records.scan` gains an optional metadata projection callback; its existing
version/session/file-size/sequence validation and explicit-path restrictions are
unchanged. The activity helper invokes this shared bounded reader separately;
unknown or incompatible transcript/state data leaves previous records intact.
No neighboring directories or parent histories are scanned. The native transcript
is decoded transiently, but no message/instruction bodies or tool results leave
the projection or enter saved state. Input bounds remain 64 MiB/file, 8 MiB/line.

`skill_activity.py` owns recording, query and enable/disable. It is a separate
installed hook command on SessionStart/UserPromptSubmit/PreCompact/PostCompact,
not additional capability logic inside `token_awareness.py`. The existing atomic
write primitive is reused. Activity uses its own namespace lock around the full
scan/merge/write, preventing concurrent stale observations from moving its cursor
backward. Atomic/fsynced writes make repeated controls/callbacks safe.

State is `<chosen-state-root>/skill-activity/<thread-uuid>.json`, schema version 1,
separate from Pi ShelfDB and the token state file. No shared DB migration occurs.
Native message ID + content-part index are dedup identity; ordinal is only an
observation/enrollment boundary. Original event time is separate from stable first
`observedAt`. Thread/session/project and provenance remain explicit. Corrupt saved
records, unexpected fields, identity conflicts and sequence rewind fail closed.

First successful observation enrolls at the current complete-record boundary.
Existing events are not imported, including inherited fork history. Resume and
hook retries preserve enrollment and prior events. `list`/`inspect` require the
explicit authorized current transcript/session and also advance observation;
these are not read-only DB queries. Filter by `--skill` before a newest-ordinal
`--limit` of 1–100 (default 20); `matchedCount` counts retained events.
`disable`/`enable` observe under the old setting first, then change it. Disabled
intervals are not backfilled. No manual record, export, deletion or import action.

`saved --state-root ROOT --thread UUID` is a separate read-only historical query.
It requires only an explicitly authorized saved thread identity, not a transcript
or session flag, and never enrolls, backfills, creates lock files/directories or
writes state. Atomic replacement by writers allows a coherent possibly stale
snapshot without reader-side locking. Results label `saved-observations-only`,
`savedThroughOrdinal`, and current coverage unknown because no transcript was
consulted. Absent state reports unknown enrollment/history without creating it.
This remains usable after the transcript disappears, rewinds or exceeds the scan
cap; tests check byte/mtime/namespace invariance and prohibit transcript scanning.

Retention is bounded to 10,000 metadata events per enrolled thread. On capacity,
additional events are skipped with `capacitySkipped`; nothing is evicted.
`disabledSkipped` and `partialTailDeferred` expose other known gaps. State can
accumulate multiple enrolled threads under the chosen root, so owner-directed
retention review remains necessary. There is no automatic expiry or global
cross-project query. Deleting active state is unsupported and would lose evidence.

The installer retains its existing `token-awareness` bundle/API name, adds the
two activity modules and a second command to each of the four event groups.
No trust/config is changed, no state is created by installation, and no skill
catalog is duplicated. Activation must explicitly authorize transcript reading
and retaining skill name/path/project/ID/time metadata, with native command trust
review. Asset updates alone are not activation. The bundled activity skill,
installed README, setup reference, CLI help and repository entry point reflect
these exact limits.

## Executable native evidence

```sh
python tests/integration/automata/codex_runtime/activity_probe.py \
  --binary "$NATIVE_CODEX_01590" --state-root "$NEW_OWNED_ROOT"
python tests/integration/automata/codex_runtime/verify_activity_probe.py \
  "$NEW_OWNED_ROOT"
```

The fixture reuses the isolated sequence harness: bubblewrap private network,
fresh HOME/CODEX_HOME, only generated fixtures/commands, loopback mock provider,
no credentials/user histories/global DB/real provider calls. Its test controller
uses native app-server stdio solely to drive the fixture; deployment needs no
custom host. Native binary location is the same recorded CX-004/CX-005 binary.

Fresh final fixture: sibling `test-state/activity-final-saved-1`. Seven actual provider
requests, none solely for activity delivery:

1. Skill catalog discovery only: zero events.
2. `$fixture-skill`: actual tagged native insertion, not a cooperative report.
3. Next prompt: installed hook's real provider request contains count 1 and exact
   session-scoped query command. Record matches native message/turn/time/ordinal.
4. Owned process restart/resume: same event ID and original observation time;
   repeated installed queries do not increment counts.
5. Missing skill selection after fixture file removal: no insertion, count stays 1.
   This proves missing-selection exclusion, not every possible read-failure mode.
6. Restore fixture skill and restart native discovery: a new actual insertion
   raises count to 2; distinct native message identity is retained.
7. Disable recording, select skill again, then enable: native transcript has the
   third insertion, retained count remains 2 and `disabledSkipped` becomes 1.

Native emitted three insertion items, two recorded and one intentionally excluded.
The installed read-only `saved` query returns the same two records, separately
labelling current coverage unknown. State contains no fixture instruction body
and creates no Pi global shelf.
Discovery/missing-file turns never manufacture native events. Unit tests also
reject successful/failed shell tool evidence, untagged fake wrappers, malformed
native metadata and state corruption, plus enrollment/backfill, fork baseline,
partial tail, concurrency, limits/filtering, capacity, replay and version mismatch.

A fresh six-request existing token/context fixture at sibling
`test-state/activity-awareness-regression-1` passes `verify_awareness_probe.py`
with both new commands installed: token acquisition, compaction exclusion,
restart/fork behavior and native context/timestamps remain intact.

## Regression command and result

```sh
PI_TEST_PACKAGE_ROOT="$INSTALLED_PI_0991" \
PI_SKILL_ACTIVITY_SDK="$INSTALLED_PI_0991/dist/index.js" \
uv run --offline --with shelfdb==3.0.2 --with dictify==5.0.2 pytest \
  tests/unit/automata/plugin tests/cli/automata/cli_test.py \
  tests/cli/automata/codex_test.py \
  tests/unit/automata/install/skills_test.py \
  tests/unit/automata/install/pi_extensions_test.py \
  tests/integration/automata/extensions/token_awareness_test.py \
  tests/integration/automata/extensions/message_timestamps_test.py \
  tests/integration/automata/codex_runtime/token_awareness_test.py \
  tests/integration/automata/codex_runtime/context_awareness_test.py \
  tests/integration/automata/codex_runtime/skill_activity_test.py \
  tests/integration/automata/extensions/skill_activity_test.py -q
```

**134 passed**: prior 97 checks, 35 new Codex checks, and two additional Pi activity
checks, including actual native Pi extension execution with isolated HOME and no
model calls. Dependencies came from the existing offline cache. Ruff and
`git diff --check` pass. No Pi implementation or existing Pi tests were changed.

This proves integration mechanics under controlled native requests, not live
model judgment or complete provider/runtime coverage. Native automatic insertion
recording is useful but deliberately narrower than all skill use. No global
installation, activation, merge, push, real-model trial or next capability is
included in this slice.
