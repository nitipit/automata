# Dual Pi / Codex support audit

Checked 2026-09-29 against Automata baseline `37acc95`, installed Codex CLI
`0.159.0`, and upstream tag `rust-v0.159.0` (commit
`687a119f0fcaace47e1f1abcc77cec6c813fd6da`). This is an audit and offline proof,
**not activation, a migration, or a claim of behavioral usability**.

Subsequent decision: [CX-008R thinking-control retirement](thinking-control-retirement.md)
revises the original parity scope to eight retained capabilities. The original
findings and recommendations below remain historical, not the current inventory.
[CX-009 native image/account evidence](account-image-native.md) subsequently proves
an ordinary-CLI image path without a duplicate wrapper; account status remains a
separate partial result, not a completed combined capability.

## Recommendation

Support ordinary Codex CLI first: retain the single flat skill catalog, shared
character components and shell tools. Preserve all Pi extensions and behavior.
Add runtime-specific guidance where a skill currently assumes Pi tools. Later,
add narrowly scoped Codex hooks/MCP only for an accepted capability and contract.
Do not adopt an Automata Codex wrapper, separate controlling app-server, custom
Codex build, general adapter framework, or duplicated catalog for this phase.

The current installer already exposes all 40 skills to Codex in an isolated
native discovery check. The current portable plugin export is recognized too.
The substantial remaining work is **runtime semantics and honest guidance**, not
moving files or mechanically translating extension APIs.

### Ordinary CLI versus a client-controlled thread

| Surface | Ordinary Codex CLI, without an Automata host | Boundary |
| --- | --- | --- |
| `.agents/skills`, `AGENTS.md`, shell CLIs | Native; candidate skill discovery tested | Discovery is not activation, judgment or successful tool use |
| Portable `plugin.json` export | Native loader recognized candidate package and skill | Local marketplace fixture only; not installed/enabled or tested through interactive plugin UI |
| Hooks | Native lifecycle mechanism; untrusted fixture was skipped | User reviews exact definitions; project trust and hook trust are separate. Positive output delivery only source/documentation evidence |
| MCP tools | Native configured server support | New MCP server adapter required for structured Automata tools; shell files in plugin metadata do not register tools |
| Context insertion from hooks | Extra developer-context messages | Persistent history insertion, not Pi's request-local message projection transform |
| Native `/model`, `/compact`, `/status`, resume/fork | Human/native alternatives | Not equivalent to model-callable Pi tools or per-compaction model selection |
| `codex queue --thread <UUID>` | Native user-message queue entry point | Source requires shared-server discovery, rejects `--no-daemon`; not a structured router/admission receipt or proven wakeup contract |
| App-server `dynamicTools`, settings, injection | Available to a connected host for owned threads | Proofs here create isolated threads, not ordinary CLI sessions; no authority or evidence to attach to user daemon/history |

Codex CLI itself uses app-server internally. “Custom host required” here means
Automata would need an explicit supported connection and ownership contract to
use those controls; it does **not** mean the APIs are intrinsically inaccessible
to a CLI. Do not turn an internal/shared-daemon endpoint into implicit authority.

## Packaging and discovery

- Keep `src/automata/skills/bundled/`, `character/`, `tools/` and
  `runtimes/pi/extensions/`. Create `runtimes/codex/` only when there is an approved
  implementation to own, not an empty mirror tree.
- Existing skill targets `.agents/skills` and `~/.agents/skills` work. Codex also
  recognizes legacy `$CODEX_HOME/skills` and bundled system skills. Prefer shared
  targets rather than adding a second installed catalog.
- Native proof found same-name repo and global fixture skills together. Source
  deduplicates paths, not names. Do not promise “nearest wins.” Audit destination
  collisions, avoid installing one skill through multiple mechanisms, and use
  explicit paths/namespaced plugin identities where ambiguity matters.
- A directory symlink to the same skill was deduplicated in the fixture. This
  does not validate arbitrary symlink escapes or all symlink install behavior.
- Codex's project instruction chain stops at the project root; within a directory
  `AGENTS.override.md` takes precedence over `AGENTS.md`. User instructions use
  the Codex home, not Pi's home. Project trust and document-size limits apply.
  Shared character **content** can be composed into each confirmed surface;
  neither runtime automatically reads the other's global `AGENTS.md`.
- Automata's compose guidance for additional instruction directories is guidance
  to read files, not an independently proven Codex automatic discovery feature.
- Existing root `plugin.json` Agent Plugins v1 export works in native loader.
  Codex gives its skill the name `automata-audit:automata-plan`. The exported
  `me.umlab.automata` tool metadata remains passive: no MCP tool registered.
- If later packaging hooks/MCP, keep portable `mcp.json` and skills at the root;
  put Codex settings under `extensions.com.openai`. Current Codex supports the
  `.codex-plugin/plugin.json` fallback, but no need to replace the portable format.
  Inline OpenAI overlay replaces, rather than merges with, that fallback.
- Keep existing copy/replace/symlink conflict semantics. Do not silently overwrite
  `config.toml`, trust hooks, install marketplaces, retire Pi assets or migrate data.

## Runtime-semantic findings

### Token awareness and context status

Pi's reference counts normalized `input + output + cacheWrite`, excludes
`cacheRead`, records immutable custom entries in active ancestry, and replays
hidden annotations at branch positions. Codex exposes a different contract:

- Local generated `ThreadTokenUsageUpdatedNotification` contains `last`, `total`,
  `modelContextWindow`; usage categories include `inputTokens`,
  `cachedInputTokens`, **`cacheWriteInputTokens`**, `outputTokens`,
  `reasoningOutputTokens`, `totalTokens`. Do not claim cache-write data is absent
  in 0.159.0; older documentation may omit it.
- Codex input is total input, not Pi-normalized uncached input. Its own
  `blended_total()` uses `max(input - cached_input, 0) + max(output, 0)`.
  A potential normalizer would subtract cached reads and writes from input,
  then add writes once; equivalently count input minus cached reads plus output
  when categories are valid subsets. Never add reasoning output again.
- Category presence alone does not prove a provider actually reported each field.
  The parser defaults missing cache-write/reasoning details to zero. Retain
  unknown/ambiguous telemetry rather than inventing zero measurements.
- Native `TokenCount` includes paths that update usage for compaction, and context
  recomputation can replace last usage with an estimate. Blindly summing `last`
  notifications or treating `total` as branch main-assistant billing is wrong.
- A separate internal `TokenUsageRecord` has response/thread/turn identifiers and
  is persisted for completed responses. That is source evidence, not a stable
  hook contract or permission to tail private transcripts.
- Lifecycle hooks expose no documented per-model-response usage event. Stop is
  a turn-stop hook, not every tool-call-only model round. Hook transcript format
  is explicitly unstable. A transcript-tail implementation would be a separately
  accepted, version-coupled compromise, not seamless native parity.
- Hook developer context is persisted; it can be compacted. No supported hook
  projects immutable branch metadata back into every future model request as Pi
  does. Thus exact token landmarks are **unavailable in the recommended first
  CLI slice**, even though useful lower-parity telemetry may be possible later.

### Model-only context, timestamps and continuity

`thread/inject_items` accepted a developer message without starting a turn.
The sentinel was stored as `response_item` in the owned thread history; native
`thread/read(includeTurns=true)` exposed zero visible turns. This demonstrates
history insertion hidden from that UI-shaped result, **not** ephemeral context,
secrecy, no disk record, or a general before-request transform.

Hooks' `additionalContext` is converted to developer messages and passed to
`record_conversation_items`. A timestamp hook could attach a stable observation
of user submission, but cannot honestly claim original timestamps for every
assistant message or rewrite retained historical messages model-only. Avoid
changing current-clock prefixes on each request.

Resume accepted the same owned thread. Fork created a new ID and inherited the
registered dynamic-tool metadata, but did **not** inherit the injected developer
sentinel in the history-only fixture. Synthetic injected user/assistant messages
are not real admitted/completed turns. Do not extrapolate that negative result
to ordinary conversation forks; it shows why injection alone is not a continuity
proof. No compaction was invoked: it is a model operation, and approval for a paid
call was absent. Resume-after-process-restart and completed-turn fork/compact
landmark continuity remain untested.

### Thinking, compaction and session controls

- Experimental `thread/settings/update` applies to subsequent turns. It accepted
  `not-a-supported-effort`, and resume returned that value. This proves only
  acceptance/persistence, not effective reasoning execution.
- `model/list` schema advertises `supportedReasoningEfforts`; any future adapter
  must validate exact model metadata, retain unknowns, reject unsupported levels,
  and report requested/persisted/effective separately. Do not map Pi's levels
  blindly to every Codex model.
- Experimental `turn/settings/update` targets a running turn and publishes for
  subsequent captures; already captured steps remain unchanged. It is closer to
  Pi's next-request timing but was not exercised without a live turn.
- `thread/compact/start` has only `threadId` in the local schema. It does not
  expose Pi's custom instructions, selected provider/model, summary-only effort,
  settled-run queue and optional resume message contract. Use native compaction
  as an alternative, not a renamed same-contract tool.
- Codex list/read/fork/archive APIs are not Pi receipt-bound copy/OS-trash tools.
  Archive is a native alternative, not deletion or verified backup. Do not map
  Pi trash to Codex permanent delete or infer inactivity from session metadata.

Subsequent [CX-007 session evidence](session-management-port.md) establishes a
separate bounded implementation: explicit-store receipts, independently
materialized copies distinct from linked fork, and genuine OS-trash packaging
before native removal with verified native restore. It does not relax the
inactivity/authorization limits or promise general Pi parity.

### Communication, hooks and tool authorization

Shared message-router service and generic browser client are runtime-independent.
Its Pi extension and `browser/pi-client.js` are not: Pi delivery metadata,
steer/followUp/nextTurn, canonical-admission confirmation, named pending slots and
wakeups need an explicit Codex contract. MCP can expose request/reply/poll tools;
it does not by itself deliver unsolicited data into an ordinary CLI model turn.
Hooks can drain a bounded pending inbox at supported boundaries without promising
immediate wakeups. Prefer untrusted-content roles: external page text must not
be promoted into trusted developer instructions simply because hooks use that role.

Tool and hook execution retain their native authorization boundaries. The
model-generated shell sandbox is not proof that MCP servers or configured hook
commands are equally confined. Treat those as reviewed local executables with
minimal filesystem/network access and explicit lifecycle. Never use approval or
hook-trust bypass flags to make tests pass. The native negative trust fixture
only proved skipping an untrusted command, not positive hook behavior.

## Implementation choices, in order

These are recommendations requiring approval, not work already implemented.
Ranges are rough solo active effort, excluding user wait and dependency downloads;
input/output estimates exclude cacheRead and are not a cost quote.

1. **Shared CLI support and guidance (recommended next): 30–60 min,
   30k–70k tokens.** Preserve flat catalog; add precise runtime dispatch to the
   seven Pi-assuming general skills, leave `automata-pi-sessions` explicitly Pi,
   update setup/support docs. Reuse existing installer/plugin exporter. Tests:
   all 40 names discover from isolated candidate source; no parent/global masking;
   duplicate warning/selection policy; existing Pi and export regressions pass.
   Acceptance must distinguish files/discovery from live behavioral usability.
2. **One ordinary-CLI hook/MCP capability: 45–90 min, 50k–100k tokens.** Choose
   either bounded inbox delivery or submission-time annotation, not all adapters.
   Pin supported Codex version, trust requirements, exact roles and lower-parity
   semantics first. Test malformed payloads, duplicate delivery, changed hook hash,
   idle/busy behavior, process shutdown and sandbox boundaries. A scripted mock
   provider could prove request contents locally only with separately approved
   scenario; it would not prove model judgment. Paid smoke test needs explicit
   model/call/token limits and isolated state, never credentials copied here.
3. **Advanced telemetry/control research: defer or separately approve.** Exact
   branch landmarks, timestamp projection and live self-control may require a
   supported host connection or upstream interface work. Do not estimate this as
   a routine extension port. First bounded acceptance question: can native CLI
   expose per-response usage and safe history-local metadata without transcript
   scraping or controlling another session? Stop if not; report unsupported.

Within the user's total 2h30m window, slice 1 and possibly one narrow slice 2 are
plausible after review/approval; full parity is not. No need to consume the window.

## Decisions needed from the owner

- Accept native CLI useful-equivalent support with explicit Pi-only advanced
  features, or prioritize a specific advanced feature for further proof?
- Prefer shared direct skill installation or plugin distribution for Codex? Avoid
  installing the same skills both ways by default.
- If continuing, approve slice 1 alone, or name the one hook/MCP outcome for slice 2.
  Hook trust/config activation, global installs and live trials remain separate.

See [inventory](inventory.md), [proof recipe](proofs.md) and the bounded
[verified native summary](native-summary.json). No production code was changed.
