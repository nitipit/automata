# CX-005: context status and timestamps via ordinary hooks

Extends accepted CX-004 (`384c6da`) without a new host, MCP server, hook family or
catalog. The user accepts sequence-linked, coverage-labelled delayed delivery,
not identical Pi projection mechanics. Pi files are unchanged.

## Implementation and source meaning

`context_records.py` projects only bounded metadata during the existing explicit,
version-pinned transcript scan. `context_awareness.py` maintains stable packets,
six recent message records and eight turn-input observations in the existing
atomic per-thread state. `token_awareness.py context` is the agent-callable
inspection path; exact authorized session/path arguments arrive in hook context.
Installer upgrades include both modules while preserving existing token state.

Pinned source `687a119f0fcaace47e1f1abcc77cec6c813fd6da`, paths under `codex-rs/`:

- `protocol/src/protocol.rs:2439–2470`: `tokens_in_context_window()` uses native
  `total_tokens`. Native UI remaining percentage subtracts a 12,000 baseline;
  our **raw last-observed tokens/window ratio is explicitly different**.
- `core/src/session/mod.rs:4846` (`recompute_token_usage`): recomputation places an estimate in
  `last_token_usage.total_tokens` with zero usage categories. This is not billing
  and is not added to the identified response ledger.
- `core/src/session/mod.rs:2601–2640`: native item completion records stable item
  and turn IDs plus started/completed epoch-millisecond lifecycle times. A missing
  native start may fall back to completion; neither is human composition time.
- `core/src/hook_runtime.rs:684–707`: UserPromptSubmit carries native turn ID and
  current transcript path. It does not supply a distinct persisted message ID or
  original user typing clock at that boundary; the packet labels a separate hook
  observation, not an invented message-creation timestamp.

## Observations and limits

Each supported hook emits at most one token snapshot and one context/timestamp
snapshot. Context fields identify native source ordinal/time; the latest known
estimate can precede incoming input, results and injected packet text. A positive
window from that same native observation is required for pressure. Native task
window can be known separately before usage exists. Missing/default-zero telemetry
produces unknown pressure, not an invented empty context. Ratios are not cache-
normalized; native cumulative usage is never used as the context numerator.

The first retained turn-input observation has a stable ID/time. Repeated callbacks
reuse it. After the bounded eight-anchor retention window, re-observation gets a
new ID rather than changing an old ID's timestamp. Same-turn steering need not
get a separate hook anchor. Native message IDs still describe recent actual items.

Message started/completed and original record timestamps are offset-aware ISO8601
UTC, distinct from snapshot `observedAt` and inspection time. No historical body
is rewritten/copied. Conflicting lifecycle times for an existing native item ID
fail coverage closed. Wall elapsed includes idle pauses; it is not active work.
Clock reversal gives unknown elapsed. Anchor usage counts only observed completed
compaction-free responses sharing the anchor's turn, with existing exclusions.

Snapshot identity ignores changing inspect clocks and the helper's own developer
text, so its output cannot recursively become larger metadata input. Replaying the
same packet does not create a new observation. Native history still stores bounded
packet text per invocation (linear growth); it is not Pi request-local projection.
There is no timer, idle wakeup or before-every-model-request pressure guarantee.

Resume/compaction retain latest useful metadata. Missing current observations can
restore last-known context/timestamps/anchor with explicit coverage; this is not
active-branch projection. Forks never follow parent paths or manufacture inherited
coverage. Corrupt awareness state gives sanitized unknown coverage without reset.
Existing token-only state is accepted and gains awareness state without changing
its counters/checkpoint.

## Executable evidence

Reuse the owned native fixture and add the combined verifier:

```sh
python tests/integration/automata/codex_runtime/sequence_probe.py \
  --binary "$NATIVE_CODEX_01590" --state-root "$NEW_OWNED_ROOT"
python tests/integration/automata/codex_runtime/verify_awareness_probe.py \
  "$NEW_OWNED_ROOT"
```

The verifier also runs all CX-004 token assertions. It checks actual provider
request bodies against native protocol item-completion events, not synthetic
packet-only metadata. The fixture installs the candidate, runs a private-network
loopback mock provider, and trusts only its generated commands in isolated HOME.
It uses no user history, real provider, credential, global config or shared daemon.

- Request 1: explicit input-observation anchor, known native task window, unknown
  context usage; no invented pressure or timestamped body rewrite.
- Request 2: native last tokens 120,025 / window 258,400 (46.449%), plus two earlier
  native item IDs/timestamps. This is not normalized token count 110,025.
- After native compaction: the recomputed context estimate replaces the previous
  response estimate; cumulative 360,075 is not mistaken for context occupancy.
- Restart/resume: six recent message timestamps retain identical values across
  packets and match native completion clocks. Fork's initial unavailable context
  and timestamps remain unknown/empty, then local observations become available.
- Installed `context` returns an inspect clock, wall elapsed and measured anchor
  usage distinct from context occupancy. Exactly six mock requests occur—five
  normal turns plus one compaction, none solely for awareness delivery.

Focused unit checks additionally exercise idempotence despite later clocks and
own developer text, timestamp collisions, bounds, missing/invalid denominators,
zero ambiguity, all pressure bands, rate-limit-only events, corruption, restored
facts, native-anchor recovery, eviction identities and token-state compatibility.
Full selected regression command is the CX-004 command plus
`tests/integration/automata/codex_runtime/context_awareness_test.py`, with the same
explicit Pi 0.99.1 package override and cached offline environment. Final candidate
checks: **97 passed**, Ruff clean, `git diff --check` clean. Fresh owned fixture
`test-state/awareness-3` passed the combined native verifier; its artifacts remain
outside tracked source. No canonical time-awareness skill was recreated.

This establishes native integration mechanics under controlled provider responses,
not live model judgment, complete real-provider telemetry or the other remaining
Pi integration behaviors. No actual user activation is performed by these tests.
