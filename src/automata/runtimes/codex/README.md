# Codex awareness, skill activity and sessions (0.159.0, Linux/POSIX)

A small ordinary CLI hook/helper integration, not a custom Codex launcher.
Requires Python 3.12+ and a local Codex 0.159.0 transcript. Pi is unchanged.
Check `codex --version` before activation and revalidate after upgrades. Transcript
metadata records creation version; it does not prove which binary later resumed
and appended to that file. Compatibility with newer writers is not assumed.

## Install and activate explicitly

From an Automata environment, with confirmed destinations and copy/replace/symlink
mode:

```sh
uv run --offline automata codex install \
  --target-root /absolute/project/.agents/codex \
  --state-root /absolute/project/.agents/var/codex-token-awareness --mode copy
```

The existing `token-awareness` bundle name is retained. It installs
`token_awareness.py`, `token_records.py`, `context_awareness.py`,
`context_records.py`, `skill_activity.py`, `skill_records.py`, the explicit
`session_management.py` control and its `session_*.py` modules, `README.md`, and a
generated `hooks.json` fragment. It does NOT edit existing Codex config,
trust commands, start sessions, create mutable state, or install duplicate skills.
State must remain outside the replaceable bundle. Symlink mode links script/docs
files; the generated fragment still records the chosen absolute destination.

Activation is a separate consent boundary: review the generated commands and
merge the four event groups into the intended Codex `hooks.json` without
replacing existing hooks. Use native `/hooks` review to trust those exact commands.
Do not bypass trust or sandbox settings. Approving activation authorizes reading
**only the current hook-supplied transcript path** and saving IDs, usage,
context metadata, timestamps and native skill-insertion metadata to the chosen
state root. The skill recorder separately enrolls at the first successful
observation; it does not backfill earlier skill events. Each event group has two
commands; review both when updating an existing installation. Neither installer
nor awareness hook scans session directories or attaches to a daemon. The separate
session-management control below has its own explicit store/selection authority;
installing it or trusting awareness hooks does not authorize session management. Changed commands need native trust review again.

## What the model receives

At `SessionStart`, `UserPromptSubmit`, or `PostCompact`, observe complete JSONL
records from the hook's explicit `transcript_path`, validate session identity and
version, and merge previously unseen response IDs. At a hook boundary where the
counted delta reaches 100,000, save one checkpoint. Additional context supplies
that snapshot without a new model request. There is no before-next-model barrier:
status can be delayed until a later prompt. The checkpoint carries:

- thread and stable response identity, measured response count and native record
  ordinal (a location, NOT response identity);
- observation timestamp distinct from the measured-through response;
- normalized categories, counted usage, threshold and delta;
- explicit coverage, skipped compaction records and unfinished/unclassified records.

The latest saved checkpoint is replayed with the **same checkpointId**, not a new
landmark, on subsequent hooks. This restores context after resume/compaction and
handles output-loss/retry without manufacturing new landmarks. It intentionally
adds persistent developer context, not Pi's request-local hidden projection.
Native context limits can remove old copies. It does not wake an idle session.

## Inspect/set from the agent

The installed helper is a shell-callable control, not a registered MCP function.
Use only the current session's explicitly supplied/authorized path and identity;
do not search for a transcript or guess another session. For example:

```sh
python3 /absolute/project/.agents/codex/token-awareness/token_awareness.py inspect \
  --state-root /absolute/project/.agents/var/codex-token-awareness \
  --transcript /explicit/current-session.jsonl --session <current-session-uuid>
python3 /absolute/project/.agents/codex/token-awareness/token_awareness.py set \
  --state-root /absolute/project/.agents/var/codex-token-awareness \
  --transcript /explicit/current-session.jsonl --session <current-session-uuid> \
  --threshold 200000
```

Set accepts integers 1–1,000,000,000, retains accrued usage and old latest snapshot,
and takes effect at the next hook checkpoint. Inspect does not create a checkpoint.
Hooks also provide an exact inspect command for the current transcript/session,
including before the first threshold is reached. Controls need permission to read
that transcript and write the selected state; hook execution permission does not
imply model shell permission. If the current path is unavailable to the agent,
ask the owner rather than discover histories.

## Context status and message timestamps

Use `context` instead of `inspect` in the same explicit helper command for the
context/timestamp diagnostic. The normal hooks automatically include a bounded
context/timestamp packet alongside token information, including before the first
token threshold. No new hook, timer, model turn, MCP server or host is required.

The context numerator comes from the most recent native
`TokenCount.info.last_token_usage.total_tokens`, **not cumulative usage** and not
the normalized response ledger. A zero/default value is ambiguous and gives
unknown usable tokens. Recomputed post-compaction estimates are identified.
Pressure is `100 * tokens / model_context_window` only when that same native
observation has a positive denominator. This is a raw last-known occupancy ratio,
NOT the native UI's baseline-adjusted remaining percentage. A separately reported
native task window can be known even before any usage observation. No cached-input
subtraction is applied to context size. Native observations can omit incoming
input, later tool results and the packet text itself.

The first retained UserPromptSubmit observation in a turn creates a stable
observation ID and offset-aware timestamp; repeated callbacks reuse it. Eight
anchors are retained. Re-observing an evicted turn creates a NEW observation ID,
not a replacement time for the old observation. This hook clock is not the user's
composition time. If no hook anchor exists, a native user item lifecycle clock
is used; if those clocks are absent, the log-record clock is explicitly labelled
instead. Same-turn steering is not promised a distinct hook
anchor; native item IDs/times still describe observed user messages.

Six recent native UserMessage/AgentMessage item IDs retain their turn, started/
completed lifecycle timestamps and original observed log timestamp/ordinal.
All times are canonical ISO8601 UTC with explicit offset. Bodies are untouched
and never copied into these packets. Conflicting lifecycle time for the same item
identity fails coverage closed instead of rewriting a timestamp. Record ordinal
is a log location, not item identity or wall time.

The packet's `observedAt` and `elapsedWallSecondsAtObservation` stay fixed on
same-ID replay. `context` additionally reports fresh `inspectedAt` and
`elapsedWallSecondsAtInspect`; elapsed is **wall time including idle**, not active
work. Clock reversal yields unknown elapsed. `anchorUsage` covers measured,
completed compaction-free responses sharing the anchor's turn; incomplete/mixed
turns remain excluded, not fabricated zero usage for the whole task.

Resume/compaction can restore recent facts and the latest packet from the same
atomic state. A missing current transcript context observation is explicitly
labelled `restored-last-known-observation`; forks do not read parent paths or copy
parent state. These are observations, not exact active-branch projections.
Packet identity excludes changing inspection clocks and ignores the helper's own
developer text, preventing recursive growth. Each hook emits at most one token
snapshot and one context snapshot with six recent timestamp records. Repeated
callbacks may append the same bounded packet; history growth is linear in hook
invocations, not a copy of prior conversation. There is no idle-time wakeup or
before-every-request pressure barrier.

## Native skill activity

The separate `skill_activity.py` hook scans the same explicit, version-pinned
transcript at the four supported events. It records only native local-file skill
instruction insertions tagged `skills.selected_skill_instructions`; no skill files
are reread. Native message ID + content-part index identify events, with skill
name/path, turn/thread/session/project, original log timestamp, observation time
and `evidenceKind: native_instruction_insertion`. Instruction bodies, user text,
tool output and credentials are not saved. This proves insertion, possibly
natively truncated, not complete-file reads, compliance or every invocation.
Discovery, failed/missing selection, ordinary user `<skill>` text, shell commands
(even successful reads/scripts), resource-backed skills and cooperative reports
are not counted. Unsupported metadata yields explicit unavailable coverage.

Hooks supply the exact authorized `skill_activity.py list` command. Use `inspect`
for the same status contract, `--skill NAME` for filtering and `--limit 1..100`
(default 20) for newest-ordinal-first events. `matchedCount` is the retained count
after filtering, not distinct sessions. Both controls read the transcript and
update recording; shell execution permissions remain separate from hook trust.
No multi-session discovery or implicit cross-project query is offered.

For a read-only historical query, use the hook-supplied `skill_activity.py saved`
command with `--state-root ROOT --thread UUID`, without transcript/session flags.
It reads only that authorized saved state file, never enrolls, backfills, creates
lock files or writes state. Skill/limit filters also apply. Output explicitly says
`saved-observations-only` and current coverage unknown because no transcript was
consulted. Missing, rewound or oversized live transcripts do not block this query;
absent state reports unknown enrollment/history without creating a directory.
Atomic writer replacement makes each read a coherent (possibly stale) snapshot.

With recording-control approval, `disable` or `enable` first observes through the
current boundary under the old setting and then changes it. Disabled events are
not backfilled on enable. First enrollment also excludes all existing history,
including inherited fork events. Later supported hooks or explicit controls catch
new insertions; no turn-end/immediate-delivery guarantee or extra model request.
Same-thread resume/retry deduplicates; counts are lifetime observations rather
than active-branch projections. Rewound transcript sequence returns unknown
coverage and retains prior state, not an automatic reset.

State is `<state-root>/skill-activity/<thread-uuid>.json` (version 1), entirely
separate from Pi's ShelfDB and the existing token ledger. A namespace lock protects
scan/merge/write against concurrent stale observations; replacement is atomic and
fsynced. At 10,000 retained events per thread, additional events increment
`capacitySkipped` without deleting existing records. `disabledSkipped` reports
known disabled events; `partialTailDeferred` labels incomplete final records.
The chosen root can accumulate multiple enrolled threads: review retention with
the owner. No automatic expiry, deletion, migration, export or backfill exists.
Do not delete active state; authorized removal loses enrollment/dedup evidence.
Zero events or missing hooks never establish that no skills were used.

## Explicit native session management

`session_management.py` is a shell control, never an automatic hook. It requires
Python 3.12+, a trusted local **Codex 0.159.0** binary and Linux `bwrap` for mutations;
trash also needs `gio`. No unsandboxed or permanent-delete fallback exists. It
starts short-lived native app-server stdio processes with private networking,
synthesized HOME/config, disabled hooks/goals/plugins/memories, and no model-turn
RPC. It does not attach to a running daemon or read real auth/config contents.

Use only authorized explicit roots; management state must be outside both the
native store and replaceable assets. These example variables are approved paths,
not implicit defaults:

```bash
HELPER=/absolute/assets/token-awareness/session_management.py
STORE=/explicit/authorized/codex-store
STATE=/absolute/project/.agents/var/codex-sessions
python3 "$HELPER" list --store-root "$STORE" --state-root "$STATE" \
  --cwd /exact/project --limit 20
```

`--all-projects` replaces `--cwd` only with broader discovery authority within
that store. `--cursor TOKEN` continues a page without filters. Listing is bounded
native-index metadata, not conversation previews or unindexed rollout discovery.
It checks indexed rollout headers (64 MiB file / 8 MiB record limits), and reports
missing roots/cwds and unavailable entries. Scope is capped at 10,000 indexed
sessions; pages at 100, default20. Native RPC responses are capped at16 MiB.
Missing directories do not authorize deletion.

Each page issues separate `copyReceipt`, `forkReceipt`, `trashReceipt`, valid for
five minutes and bound to store identity, caller, selected file/row snapshot and
that page. New listings/pages supersede old receipts; mutation consumes its action
receipt. Keep `CODEX_THREAD_ID` or supply known `--current-thread UUID` for listing
and mutation. Never hide the current session. All mutations require explicit
`--binary /absolute/native/codex --ids UUID ... --inactive-owned`; the latter
attests previously established ownership/inactivity, not a liveness detector.
Only a genuinely outside-session caller may use `--outside-session` instead.

| Action | Additional arguments | Result |
| --- | --- | --- |
| `copy` | `--receipt COPY_RECEIPT --target-cwd EXISTING_DIR` | Fresh independent materialized session in the same store; source intact |
| `fork` | `--receipt FORK_RECEIPT --target-cwd EXISTING_DIR` | Explicit linked native fork, not independent copy |
| `trash` | `--receipt TRASH_RECEIPT --xdg-data-home AUTHORIZED_XDG_DATA_HOME` | Verified OS-trash recovery package, then selected native removal |
| `restore` | `--recovery-id RECOVERY_UUID` | Exact selected original paths/IDs restored and natively verified |

For example, after selecting an inactive owned session from the current page:

```bash
python3 "$HELPER" copy --store-root "$STORE" --state-root "$STATE" \
  --binary "$NATIVE_CODEX" --current-thread "$CURRENT_THREAD" --inactive-owned \
  --receipt "$COPY_RECEIPT" --ids "$SELECTED_UUID" --target-cwd "$DESTINATION"
```

Destination must exist, differ from source cwd, and neither contain nor be within
the store. No project files, external assets or historical path rewriting. Copy
uses a byte-identical private source snapshot, a native-generated fresh header
(identity/cwd/provenance), and the original exact record tail instead of native
reference backing. Source-free native hydration and full canonical history digest
must match before exclusive publication; the published native history is checked
again. Plain native fork remains linked and is never substituted for copying.

Copy/trash support only materialized paginated history with no unresolved
`history_base`. Archived/pinned/project/section/agent-enriched state and ancillary
goals, queues, memories, attachments or dynamic tools lack certified recovery and
are rejected. Trash checks both spawn edges and actual history references across
**all indexed headers in the selected store**, even outside the listing cwd.
Unknown unrelated schema/header data can conservatively block removal. Unselected
dependents always reject; fully selected dependency groups are also unsupported.
A provenance-only `forked_from_id` on a materialized copy is not a data reference.

Recovery stages only selected rollouts/metadata/signatures, fsyncs them, and
verifies genuine `gio trash` contents plus `.trashinfo` before native deletion.
The chosen XDG trash and staging must share a filesystem; unsupported layouts
fail without fallback. Restore refuses path/row collisions, checks bundle hashes,
reinstates the exact original path, then uses targeted native resume to rebuild
SQLite/history projections. Original thread/turn/item IDs, name, full canonical
turn/item content digest and original rollout-byte prefix are verified. No fields
are excluded from that digest. A JSONL-only copy-back is not a usable restore.
Operational logs/caches, external assets and arbitrary runtime state are excluded.

Results are per ID: success, failure or not-attempted. Stop on partial/unknown
outcomes; do not retry automatically or delete a partially published destination.
The helper's namespace lock does not establish other-process inactivity. Receipt
validation and source rechecks reduce stale selections, not concurrent-writer
risk: callers must establish inactivity before mutation.

State contains private metadata snapshots/locks, `copies/<new-id>.json` provenance,
`recoveries/<recovery-id>.json` journals, and staging/recovery locations. Recovery
packages contain selected original conversation records; signatures store only
SHA256 plus counts, not an extra raw history dump. Temporary native/copy-validation
stores are disposed; successful restore retains the OS-trash package. Retention
may grow across operations. Owner approval is required before removing recovery
state/packages; no automatic expiry or trash-emptying is provided.

## Honest token accounting and recovery

Only identified `token_usage_record.usage` is counted. Aggregate/replayed
`token_count`, context estimates, turn/thread totals and reasoning subsets are
never added. Codex input includes cache reads and writes: normalized input is
`input_tokens - cached_input_tokens - cache_write_input_tokens`; counted is
`input_tokens - cached_input_tokens + output_tokens`. Invalid/missing fields are
unknown, not zero. Native Codex itself may default absent provider details to
zero; the adapter cannot recover that lost distinction and says so.

Purpose filtering is conservative: only completed turns without any compaction
marker count. A `PreCompact` hook durably marks the turn before compaction, so
failed attempts are excluded too; it inserts no prompt text. Entire
compaction-containing turns are excluded, **including main work mixed into those
turns**, avoiding summary/retry contamination. Historical failed attempts without
these hooks or surviving native markers cannot be certified as main-only; local
historical coverage is always labelled, not assumed complete. Unfinished
turns wait until a later observation; failed/aborted turns remain excluded.
Unreported usage is not fabricated. This is measured local coverage, never a
claimed exact whole-thread total.

Same-thread resume deduplicates by response thread+ID. Session-tree identity and
thread identity are validated separately. Saved observed records and latest
checkpoint survive transcript truncation/compaction. This is a **lifetime observed
ledger, not active-branch totals** after rollback/rewrite; inspect reports records
retained but absent from the current snapshot. Conflicting replay fails closed.
Forks use their
own state; visible completed inherited records can be counted, but referenced
ancestor files are never followed. A missing inherited baseline stays explicitly
unknown, not silently treated as exact zero. No automatic parent-state copying.

Input is a fixed-size snapshot of a regular, non-symlink file, at most 64 MiB and
8 MiB per record; partial final lines are deferred. Unknown version, malformed
schema, identity conflicts and corruption return coverage-unavailable without
resetting previous state. Only usage/IDs/ordinals, timestamps and context metadata
persist; never conversation bodies or hook prompts. Per-session file locking and atomic/fsynced state writes
protect concurrent hooks and controls. State contains a dedup ledger and grows
with observed responses; review retention deliberately. Do not delete it while a
session is active, and do not expect dedup/replay after authorized deletion.

## Verification scope

Repository `sequence_probe.py` runs native Codex with a private-network loopback
mock provider and self-trusted generated hooks, never real credentials or user
histories. Actual request bodies establish token-packet delivery; controlled
usage establishes normalization. `verify_awareness_probe.py` additionally checks
actual native lifecycle timestamps, context estimates before/after compaction,
bounded resume replay, fork unknowns and installed `context` inspection. This
proves integration mechanics, not live provider completeness or model judgment.
`activity_probe.py` plus `verify_activity_probe.py` additionally prove installed
automatic skill recording, discovery/missing-selection exclusion, stable native
evidence, restart dedup and enable/disable through seven controlled requests.
No global activation is implied by the tests.
