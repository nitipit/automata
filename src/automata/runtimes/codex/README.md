# Codex token awareness (0.159.0, Linux/POSIX)

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

This installs `token-awareness/{token_awareness.py,token_records.py,README.md}`
and a generated `hooks.json` fragment. It does NOT edit existing Codex config,
trust commands, start sessions, create mutable state, or install duplicate skills.
State must remain outside the replaceable bundle. Symlink mode links script/docs
files; the generated fragment still records the chosen absolute destination.

Activation is a separate consent boundary: review the generated commands and
merge the four event groups into the intended Codex `hooks.json` without
replacing existing hooks. Use native `/hooks` review to trust those exact commands.
Do not bypass trust or sandbox settings. Approving activation authorizes reading
**only the current hook-supplied transcript path** and saving IDs/usage to the
chosen state root. Neither installer nor helper scans session directories or
attaches to a daemon. Changed commands need native trust review again.

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

## Honest accounting and recovery

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
resetting previous state. Only usage/IDs/ordinals persist; never conversation
bodies or hook prompts. Per-session file locking and atomic/fsynced state writes
protect concurrent hooks and controls. State contains a dedup ledger and grows
with observed responses; review retention deliberately. Do not delete it while a
session is active, and do not expect dedup/replay after authorized deletion.

## Verification scope

Repository `sequence_probe.py` runs native Codex with a private-network loopback
mock provider and self-trusted generated hooks, never real credentials or user
histories. Actual request bodies establish token-packet delivery; controlled
usage establishes normalization. This proves integration mechanics, not live
provider reporting completeness or model judgment. No global activation is
implied by the tests.
