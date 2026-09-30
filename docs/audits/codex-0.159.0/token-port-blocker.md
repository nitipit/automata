# CX-003: token-awareness port boundary

Checked 2026-09-30 against native `codex-cli 0.159.0` and public source commit
`687a119f0fcaace47e1f1abcc77cec6c813fd6da`. Source paths below are relative to
`codex-rs/`. This is a blocked implementation finding, not an installed port.
Pi implementation and the shared skill/tool catalog are unchanged.

## Required behavior

The reference is `src/automata/runtimes/pi/extensions/token-awareness.ts`:
main-assistant response accounting (including tool-call-only rounds), default
100,000 counted input + output + cacheWrite, separate cacheRead, model-callable
inspect/set, one immutable landmark at the next turn-end/context boundary,
no extra model request, ancestry-aware fork/resume and compaction replay.

## Ordinary CLI fails the integration gate

- `hooks/src/schema.rs:102–127` enumerates hook events. There is no
  response-completed or before-model-request hook. Tool hooks are not response
  hooks: zero/multiple tools and interrupted responses defeat that substitution.
- `hooks/src/events/stop.rs:28–39` and `hooks/src/schema.rs:588` carry no usage.
  `core/src/session/turn.rs:647–654` runs Stop only when `!needs_follow_up`, not
  after each tool-call-only assistant round. Blocking Stop with continuation
  explicitly continues sampling (`:666–684`), violating no-extra-call behavior.
- `core/src/hook_runtime.rs:849–873` converts additional context into developer
  messages and records them in conversation. It does not project immutable
  annotations from branch metadata into each request. Persistent context alone
  cannot establish compaction replay or exact historical placement.
- `core/src/session/mod.rs:4752–4864` exposes internal accounting, including
  `TokenUsageContributor`; this is compiled Rust integration, not a loadable
  ordinary CLI plugin/hook/MCP interface. A new MCP inspect/set tool would not
  supply the missing automatic accounting and projection boundaries.

No installer, hook or MCP adapter was added: distributing controls without an
actual supported usage source and lifecycle contract would misrepresent the
requested slice. No user histories, daemon, credentials or webhook were read.

## Stronger host evidence, but not a solved alternative

`protocol/src/protocol.rs:1931–1940` defines `RawResponseCompletedEvent` with
response ID and optional exact usage, unlike estimated/accumulated TokenCount.
`app-server-protocol/src/protocol/common.rs:1959` exposes
`rawResponse/completed`; `v2/thread.rs:163–165` has experimentalRawEvents opt-in.
`app-server/src/request_processors/thread_lifecycle.rs:322–334` suppresses raw
completion notifications unless enabled. This is an owned app-server subscription
route, not a lifecycle callback delivered to an ordinary CLI hook or MCP server.

Even that route needs additional proof:

- `core/src/compact.rs:814–822` and `core/src/compact_remote_v2.rs:467` also record
  raw completions for compaction. Response identity solves deduplication, not
  main-assistant versus summary classification by itself.
- `app-server/src/request_processors/token_usage_replay.rs:1–55` replays TokenCount
  when attaching. Summing last notifications double-counts restored snapshots;
  recomputed context estimates are not response usage either.
- `core/src/session/mod.rs:4770–4795` persists identified TokenUsageRecord entries
  after sending raw completions. Durable resume/fork accounting therefore needs
  an explicit replay/recovery contract; an in-memory notification counter is not
  enough. No user-transcript scanning is authorized.
- `core/src/codex_thread.rs:751–798` injects persistent history without run_turn;
  `app-server/src/request_processors/turn_processor.rs:974–1004` gates injection.
  Neither proves a race-free per-model-step barrier or request-local projection.
  Prior history-only fork probe did not preserve the injected developer sentinel;
  completed-turn fork, compaction and restart remain untested.

For valid disjoint cache subsets, normalization is uncached input = inputTokens
minus cachedInputTokens minus cacheWriteInputTokens; counted = inputTokens minus
cachedInputTokens plus outputTokens. Do not add cache writes or reasoning twice.
`codex-api/src/sse/responses.rs:116–150` defaults absent cache-write/reasoning
telemetry to zero, so reported zeros retain provider-availability ambiguity.

## Bounded host investigation: decisive ordering gap

Following the manager's narrower authorization, source tracing established:

- **No supported universal gate.** `core/src/session/mod.rs:2575–2582` delivers
  events through `tx_event.send`, without waiting for client acknowledgement.
  `core/src/session/turn.rs:2934–2960` records completion and returns to the
  internal loop. The loop drains pending input, captures a step, clones history,
  and invokes sampling (`:428–532`) without a host checkpoint handshake.
- **Injection is not a barrier.** During an active turn,
  `core/src/session/inject.rs:74–99` queues client items for a future pending-input
  drain. A host reacting to raw completion can lose the race against the next
  drain/request. RPC acceptance is not proof of next-request inclusion.
- **Tool/approval waits cannot close the general gap.** Server request definitions
  (`app-server-protocol/src/protocol/common.rs:1762–1832`) offer tool execution,
  approvals, authentication, attestation and external clock reads, not a universal
  response-checkpoint acknowledgement. Tool-free continuations are possible
  (`core/src/session/turn.rs:2953–2955`, `end_turn=false`). Forcing a model to call
  a dynamic token tool is neither automatic nor a no-extra-call guarantee.
- **External clock is not an annotation gate.** The clock request has a ten-second
  timeout (`app-server/src/current_time.rs:25,85–139`). It is a time-provider
  contract, not history mutation. Even delaying it would happen after the loop's
  input drain, while active injection still queues items; hijacking that callback
  does not establish correct-boundary insertion.

Thus an app-server launcher alone cannot guarantee the exact landmark boundary
using the inspected protocol. This is a source-level integration impossibility
for the current proposed event/inject route, not proof that a custom upstream
implementation could never support it.

### Capability matrix

| Requirement | Classification | Evidence / remaining limit |
| --- | --- | --- |
| Identified per-response usage | Exposed, experimental/internal-only | `v2/thread.rs:1883–1895`; exact optional usage, no role/purpose field; no live dispatch trial |
| Inspect/set tool | Protocol-supported | Existing dynamic tool registration proof; actual model dispatch not tested |
| Before-next-model checkpoint | Unsupported by inspected host route | Autonomous sampling loop and queued injection above; notifications have no ACK barrier |
| Main versus compaction usage | Partially observable, recovery unknown | Compaction item starts before sampling (`compact_remote_v2.rs:232–245`); both compaction paths record raw usage; failed/reconnected streams need durable provenance |
| Resume/fork usage baseline | Native internal restoration supported | `session/mod.rs:1557–1628` restores latest usage on resume/fork, including inherited prefix; not an external branch response ledger |
| External exact response replay | Not exposed by inspected history APIs | `thread_history.rs:422–437` ignores TokenUsageRecord; read returns projected Thread, and attach replays TokenCount rather than identified completions |
| Immutable landmarks across compaction | Not provided | Persistent developer insertion is not branch metadata projection; retention feature is bounded and experimental |

A relevant partial mitigation must not be omitted:
`retain_client_developer_messages` is under development and disabled by default
(`features/src/lib.rs:1849–1852`). Client developer items acquire provenance in
`session/inject.rs:101–110`; remote compaction/new-window code retains some of
these. But `session/mod.rs:4605–4619` truncates them to a retained-message token
budget. This is not immutable, unlimited branch landmark replay, and does not fix
the sampling race. No feature was enabled in a user configuration.

## User-visible equivalent versus exact Pi semantics

A useful lower-parity outcome is feasible in principle; this is not a blanket
no-port verdict. Inspect/set through MCP can give the agent an explicit threshold
control and measured-usage report. At the next **host-controlled user-turn
admission**, a host can await an idle injection response before submitting that
user input. This provides a landmark without starting a model call solely for
that landmark. Native injection and tool registration have idle metadata proofs;
positive MCP dispatch and completed-turn behavior remain untested.

This would differ materially from Pi:

- Landmarks arrive on the next user turn, not necessarily the very next model
  round. A long tool loop can exceed the threshold substantially before notice.
- Developer annotations are persistent context; compaction can remove/truncate
  them. Reinjecting a current cumulative snapshot is possible, but is not replay
  of immutable landmarks at original branch positions.
- An owned host can collect identified live raw usage into its own durable ledger.
  Correct interrupted-compaction classification, disconnect/crash gaps and fork
  prefixes still require proof or an explicit partial-coverage response. MCP
  itself neither supplies those events nor repairs the missing replay API.
- A host can serialize its own user-turn submissions, not another CLI client's
  autonomous activity. Ordinary CLI MCP + UserPromptSubmit alone still lacks a
  supported usage source. A transcript reader would be a distinct version-coupled
  alternative needing explicit history/privacy authority, not an implicit part
  of this proposal.

Consequently a **next-user-turn, coverage-labelled token monitor** is a concrete
functional-equivalent candidate if the user accepts changed timing/persistence
and an owned-host workflow (or separately scoped transcript coupling). It should
expose incomplete coverage, never silently reset counters or claim exact totals.
It is not an authorized relaxation or a completed implementation.

## Actionable architectural choice

**A. Preserve exact acceptance:** do not adopt a custom launcher merely to finish
this slice; current host primitives still miss exact timing and recovery.
Authorize a narrowly scoped upstream runtime-extension design/patch instead:

1. Atomic after-response checkpoint before the next input capture, including
   tool-call-only rounds, with safe annotation insertion and no new model call.
2. Durable response identity, main/summary provenance and branch-prefix replay
   cursor across resume, fork, compaction and crashes.
3. Branch metadata and request projection for landmarks/thresholds, with explicit
   registration of the model-callable inspect/set control.

Exposing these through ordinary CLI hooks/plugins would preserve the user's
normal launch workflow. Using an upstream-patched owned app-server is a fallback
with additional launcher ownership and installation costs, not an implementation
already approved or proven.

**B. Approve the useful-equivalent contract above:** first validate an owned
host's next-user-turn admission, durable ledger coverage and inspect/set dispatch;
then implement its installer. This changes workflow and deliberately relaxes
landmark timing/persistence. If ordinary CLI workflow is mandatory, separately
consider transcript coupling rather than promising an MCP-only usage solution.

Recommendation under current exact acceptance is A; choose B only through an
explicit user decision. Neither choice has been implemented. No synthetic ledger
or installer was built.

No additional idle app-server probe was run: an idle fixture cannot exercise the
autonomous model-step race or prove completed-turn recovery, and source evidence
was decisive within the bounded investigation. A future implementation would
need separately approved isolated model/mock-provider trials and failure tests.

## Verification limits

This finding is source inspection plus a native version check, not live behavior.
No model calls, compaction calls, daemon attachment, trust/config changes, global
installation or custom host implementation occurred. No production source changed.
The acceptance criteria remain blocked, not completed by this evidence document.
