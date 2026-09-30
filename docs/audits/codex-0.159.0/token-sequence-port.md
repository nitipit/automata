# CX-004: working sequence-linked token integration

The user accepted delayed delivery, sequence-linked coverage and latest snapshot
restoration rather than identical Pi projection mechanics. This is an actual
ordinary Codex CLI hook/helper implementation, not an app-server launcher. Pi and
the single shared catalog remain intact. Supported runtime: Codex 0.159.0 on
Linux/POSIX with Python 3.12+ and a local transcript.

## Shipped slice

- `src/automata/runtimes/codex/token_records.py`: bounded explicit-path reader,
  version/session validation, stable response identity and normalization; ignores
  aggregate TokenCount and excludes compaction-containing/unfinished turns.
- `token_awareness.py`: per-thread locked/atomic ledger, 100,000 default threshold,
  inspect/set shell controls, latest checkpoint replay with stable checkpointId.
- `src/automata/install/codex.py` and `automata codex install`: copy/replace/symlink
  assets and a generated hooks fragment, without config/trust activation.
- Installed `README.md` and shared setup/context-status guidance document scope,
  consent, recovery, sequence semantics and coverage limits.

SessionStart/UserPromptSubmit/PostCompact supply context. PreCompact records
turn provenance, including for failed attempts, without prompt insertion. Hook
context supplies the exact current-session inspect command; no transcript search
or MCP registration is needed. Inspect/set are real shell calls, subject to the
model's usual filesystem/sandbox permission, not claimed native function tools.

## Native boundary proof

`tests/integration/automata/codex_runtime/sequence_probe.py` installs the candidate
assets into a new task-owned root. Bubblewrap exposes only that root, system
libraries/binaries and the pinned native Codex executable. A loopback mock provider
runs **inside the private network namespace**. No external network, credentials,
user HOME, daemon or existing histories are exposed. The mock uses controlled
provider-reported usage, not a claim about tokenizer/billing accuracy.

The fixture obtains native hook hashes then trusts only its self-created commands
in the isolated HOME. It runs five normal turns and one explicit compaction,
including process restart/resume and a completed-turn fork. App-server is solely
the test driver; production is the ordinary native hook mechanism.

```sh
python tests/integration/automata/codex_runtime/sequence_probe.py \
  --binary "$NATIVE_CODEX_01590" --state-root "$NEW_OWNED_ROOT"
python tests/integration/automata/codex_runtime/verify_sequence_probe.py \
  "$NEW_OWNED_ROOT"
```

The verifier checks actual provider request bodies and installed-helper output:

- Request 2 contains checkpoint through `resp_1`, counted 110,025.
- Codex categories 120,000 input / 10,000 cached-read / 2,000 cache-write / 25 output
  normalize to 108,000 uncached input + 2,000 write + 25 output. Reasoning (5) is
  already within output; aggregates and cache reads are not added again.
- Request after compaction contains through `resp_2`, counted 220,050; summary
  `resp_3` is excluded. Inspect after next response yields 330,075.
- Installed set raises threshold to 1,000,000 without resetting usage.
- New native process resumes; inspect counts four main responses (440,100), not
  replayed aggregates, and latest checkpoint ID/content remains unchanged.
- Fork counts its one local response (110,025), separately from the parent, and
  explicitly reports unknown inherited baseline. No ancestor files are followed.
- Exactly six mock requests occurred. Checkpoint emission itself started none.

Raw request/protocol artifacts stay in the owned test root, not committed.
The verifier emits only a bounded boolean/count summary. Latest validated fixture
at the initial milestone: `sequence-8` in sibling task-owned test-state.

## Targeted checks

Focused Python/CLI/installer/parser checks plus the existing Pi/plugin/skill subset
passed **69 tests**, using explicit Pi 0.99.1 `PI_TEST_PACKAGE_ROOT` and cached
`uv run --offline`. Ruff and `git diff --check` passed. Coverage includes malformed
nested events/state, sanitized errors, missing usage/version/session mismatch,
partial tails, oversized input, compaction provenance, dedup, threshold behavior,
rollback retention labels, separate thread/session identities and installer
conflicts. The native probe is opt-in, not silently launched by pytest. Exact focused command
(the extra CLI installer test explains 69 versus the prior 68-check subset):

```sh
PI_TEST_PACKAGE_ROOT="$INSTALLED_PI_0991" uv run --offline pytest \
  tests/unit/automata/plugin tests/cli/automata/cli_test.py \
  tests/cli/automata/codex_test.py \
  tests/unit/automata/install/skills_test.py \
  tests/unit/automata/install/pi_extensions_test.py \
  tests/integration/automata/extensions/token_awareness_test.py \
  tests/integration/automata/extensions/message_timestamps_test.py \
  tests/integration/automata/codex_runtime/token_awareness_test.py -q
```

## Limits and operator decisions

No global installation or real config/trust change was performed. Asset installation
is not activation; activation specifically authorizes reading the current supplied
session path and saving usage/IDs in the chosen state root. No content bodies are
persisted by the adapter. Fixture artifacts contain only generated conversations.

Accounting is a **lifetime observed ledger**, not active-branch ancestry after
rollback/rewrite. Retained-but-absent records are reported. Purpose filtering drops
whole mixed compaction turns, including their main work. Historical failed attempts
without the adapter's PreCompact marker or surviving native provenance cannot be
certified main-only; historical/fork completeness is explicitly unknown. Missing
provider telemetry is not fabricated; Codex's own defaulted zeros remain ambiguous.

Transcripts over 64 MiB, records over 8 MiB and unsupported/malformed inputs yield
coverage unavailable rather than scanning unboundedly or resetting totals. Only
complete lines at the observation boundary are processed. Context packets may
arrive later, be replayed, or be compacted out; their through-response labels and
stable IDs distinguish measurement coverage from delivery/observation time.

This proves native acquisition and context delivery with controlled offline
responses, not live model judgment/provider completeness, every compaction
implementation or every fork/storage mode. It does not claim the other eight Pi
integration behaviors have been ported. No custom user-facing host was adopted.
