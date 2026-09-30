# Native Codex CLI setup and support

Use ordinary Codex CLI with shared Automata guidance and shell tools. No Automata
wrapper, custom app-server host, Pi extension or separate Codex catalog is needed.
Identify the host, not the model name: Pi running a Codex model is still Pi.

These instructions describe shared support and the optional token/context/timestamp
and skill-activity integration, plus explicit session management, checked against
Codex **0.159.0**. Native discovery and token hook
acquisition/delivery were verified offline with a controlled mock provider;
live agent behavior and live image quality/entitlement were not tested. Native
image invocation and copying were separately verified with a synthetic image.
Recheck version-dependent controls if your installed Codex differs; do not silently
transfer compatibility claims.

## Choose scope and exposure

Confirm selected assets, destinations and mode before installing. The commands
below are examples, not permission to run them. Run `uv run automata ...` from an
Automata checkout/environment; use an absolute target for a different project.
Use cached dependencies with `uv run --offline` when downloads are not authorized.

| Asset | Repository | Global |
| --- | --- | --- |
| Shared skills | `<project>/.agents/skills` | `~/.agents/skills` |
| Shared shell tools | `<project>/.agents/tools` | `~/.agents/tools` |
| Codex character instructions | `<project>/AGENTS.md` | `$CODEX_HOME/AGENTS.md` (default `~/.codex/AGENTS.md`) |
| Pi character instructions | `<project>/AGENTS.md` | `~/.pi/agent/AGENTS.md` |

Prefer one exposure for each skill: **direct shared installation** is the simplest
choice for both runtimes; **plugin export** is an optional packaging alternative.
Inspect relevant selected destinations and existing plugin selections first.
Codex can discover same-name skills from both repository and global roots; it does
not promise nearest-wins precedence. Legacy Codex skill roots or plugin copies can
add another exposure. Do not duplicate an installed skill merely to enable Codex,
remove existing assets without permission, or assume an installer collision check
resolves runtime ambiguity. Select portable skills plus the runtime-specific
contracts actually needed. `automata-pi-context-compaction`,
`automata-pi-context-status`, `automata-pi-skill-activity` and
`automata-pi-sessions` require their Pi extensions; they do not describe these
Codex hooks. `automata-codex-sessions` covers native Codex's separate bounded
contract. Native observation/helper details belong in the installed README,
not runtime branches inside portable skills. Full-catalog installation remains
explicitly available; the installer does not auto-detect the host or filter it.

## Direct shared installation (recommended)

For a repository, choose a small initial set or the explicitly approved full
catalog. For example, from the Automata environment:

```bash
uv run automata skills install \
  --target-root /absolute/project/.agents/skills \
  --skill automata-plan,automata-software-development,automata-setup \
  --mode copy
```

For a global installation, use `--target-root ~/.agents/skills` instead. Omit
`--skill` only when all bundled skills are approved. Shared skill installation
needs no Codex-specific switch. `copy` and `symlink` require absent selected destinations;
`replace` removes selected existing destinations before copying, not merging.
A symlink exposes source changes; it is not a runtime reload command.

Install companion shell tools only for selected capabilities, for example:

```bash
uv run automata tools install \
  --target-root /absolute/project/.agents/tools --tool timer --mode copy
uv run --offline --no-project --script \
  /absolute/project/.agents/tools/timer/timer.py --help
```

A skill's `.agents/tools/...` mapping points to a shell entry, not a registered
Codex function. Resolve it against the selected project or global install root,
not the skill directory. Dependencies, executable availability, sandbox file/socket
permissions and any browser/network access remain capability prerequisites.
Do not loosen sandbox/approval settings to make a tool appear ready. `--help` is
not a scheduler, browser, messaging or external-effects acceptance test.

## Optional sequence-linked awareness and skill activity

With explicit asset/state roots and mode approved:

```bash
uv run --offline automata codex install \
  --target-root /absolute/project/.agents/codex \
  --state-root /absolute/project/.agents/var/codex-token-awareness --mode copy
```

This installs the `token-awareness` helper, README and generated hooks fragment;
it does not modify Codex configuration/trust. Review the installed README before
activation. Separately authorize merging its SessionStart/UserPromptSubmit/
PreCompact/PostCompact groups into the intended hooks file and reviewing commands
with native `/hooks`. Activation authorizes reading the current hook-supplied
session transcript only, retaining usage/context/time and native skill-insertion
metadata, not bodies. Review both commands per event when updating an existing
installation: the skill recorder is separate and starts enrollment without
historical backfill. No broad history discovery or daemon attachment occurs.

The agent receives token threshold snapshots linked to response ID/record ordinal,
and bounded context/timestamp packets, plus exact current-session shell controls:
`inspect`/`set` for token accounting, `context` for the context/time diagnostic. Delivery is delayed to a
supported hook boundary; no extra model turn is requested. Default counted
threshold is 100,000 with Codex cache normalization, not Pi's raw category sum.
Aggregate snapshots are ignored. Completed compaction-free turns are measured;
entire mixed/compaction turns and unknown telemetry are excluded. PreCompact
saves provenance so failed compaction attempts can also be excluded.

The dedup ledger preserves lifetime observations, not exact active-branch totals
after rollback. Latest checkpoint replay uses the same ID after resume/compact.
Forks have separate state and report unknown inherited coverage when ancestor
records are unavailable; the helper never follows ancestor paths. State contains
usage/IDs, not conversation bodies. Bounded reads/version checks fail closed with
coverage unavailable, retaining previous state. Review ledger retention before
cleanup; no automatic deletion. Normal shell sandbox permissions still apply to
agent inspect/set calls even when hook execution is trusted.

Context pressure uses native last-usage/recomputed tokens and its positive window,
not cumulative billing or the token ledger. Raw occupancy is not Codex UI's
baseline-adjusted remaining percentage. Missing/default-zero telemetry stays
unknown. Stable native user/assistant item IDs retain lifecycle/record times;
current input observations use a separately labelled hook clock. The latest six
message times and eight input anchors are bounded; replay does not change original
timestamps or infer active work from wall elapsed. Same-turn steering need not
receive a separate hook anchor. A re-observation after anchor eviction gets a new
ID, and restored facts remain explicitly last-known, not a branch projection.

This is a tested version-coupled useful equivalent, not full Pi runtime parity or
certified live-provider usage. Existing token state is preserved when adding the
context/timestamp module; new fields live in the same atomic state. Review changed
asset behavior before an approved update, without enabling config implicitly.
The separate `skill_activity.py` helper automatically records successful native
local skill instruction insertions using tagged metadata, not shell intent or
available-skill lists. Hook context provides the current-session `list`/`inspect`
command; `--skill NAME` and `--limit 1..100` filter bounded results. These controls
also update the observation. The separate `saved --state-root ROOT --thread UUID`
query reads only an explicitly authorized saved thread snapshot, with no transcript,
enrollment or writes, and labels current coverage unknown. Use it for historical
records even when the live transcript is unavailable. Authorized `disable`/`enable` controls do not backfill
disabled events. Records carry Codex runtime/provenance, native message/turn IDs,
name/path/project and original/observation timestamps. They prove insertion, not
Pi complete-read semantics, every invocation or compliance. Shell reads, scripts,
resource-backed skills and cooperative reports are not counted.

State is separate under `<state-root>/skill-activity/`, with per-thread enrollment
and dedup; the Pi database and token ledger are unchanged. First enrollment skips
existing and inherited history. At 10,000 records per thread, capacity skips are
reported without eviction. Review retention with the owner; no automatic deletion
or cross-project query is provided. Missing hooks or zero records mean incomplete
coverage, never proof of no skill use. Other integration behaviors remain below.

## Optional explicit session management

The same approved asset installation includes `session_management.py` and its
modules under `token-awareness/`; it adds no hook actions or activation. Review
its installed README. The shell control uses explicit native-store and private
management-state roots, exact-cwd or authorized all-projects metadata listing,
page-bound one-use receipts, selected IDs, and established inactivity/ownership.
State must be outside the native store and replaceable bundle. No implicit global
store or real configuration/credential access is used.

On Linux with `bwrap`, the pinned binary provides short-lived isolated management
RPC without model turns. `copy` produces a verified independent materialized
history in the same store with fresh identity/destination cwd; explicit `fork`
remains linked and is not a copy substitute. Both preserve source records and
historical paths, and copy no project files. `trash` requires `gio` and an approved
XDG data home; a genuine OS-trash recovery package is verified before native
delete. `restore` rebuilds native history projections and verifies complete
history content/IDs, name and original byte prefix, not just JSONL presence.

Before removal, dependency checks inspect other indexed headers in the selected
store; authority to mutate still covers only receipt-selected IDs. Unselected
dependents, selected dependency groups, archived/enriched/ancillary state and
unknown schema fail closed. Caller attestation is not other-process liveness
proof. Partial outcomes require review without automatic retry or cleanup;
recovery packages remain until separately approved retention cleanup. This is a
narrow native contract, not Pi parity. The `automata-codex-sessions` guidance is
part of the single shared skill catalog, with no duplicate Codex catalog.

## Character content, distinct instruction surfaces

Compose once for review using the chosen character components:

```bash
uv run automata character compose \
  --personality automata --language thai --behavior co-pilot
```

The command prints Markdown; it does not edit instructions. Only with separate
approval, place or merge reviewed content into the chosen `AGENTS.md` surface.
Do not overwrite an existing file by blindly redirecting stdout. Shared repository
content can serve both hosts, but neither reads the other's global file.

Codex's project chain is root-bounded; `AGENTS.override.md` takes precedence over
`AGENTS.md` in a directory. Trust and document-size limits affect loading. The
composed additional-instruction-directory guidance is an instruction to read
files, not a promise of automatic native Codex discovery. Verify the intended
surface rather than copying Pi's global path into Codex configuration.

## Optional plugin packaging

Export selected skills using the existing portable Agent Plugins format:

```bash
uv run automata plugin export \
  --name automata-selected --skill automata-plan \
  --output /absolute/output/automata-selected
```

This creates a package; it does **not** install or enable it in Codex. Registering
a marketplace or installing/enabling a plugin is a separate authorized native
Codex operation. Consult the installed version's plugin interface for that step;
this slice does not establish an interactive installation recipe. Prefer direct
installation above when a verified file-placement path is wanted.

The 0.159.0 native loader recognized the portable `plugin.json` and namespaced
skill from an isolated local marketplace fixture. The package was not enabled,
and no behavioral activation was proven. Exported `me.umlab.automata` tool metadata
is passive: shell files do not become MCP tools. No hooks or MCP adapters are
installed by this route. Avoid selecting the same skill through both mechanisms.

## Support boundaries

Assess useful task capacity, not a count of matching Pi extensions. The optional
hooks/helpers have offline evidence for token awareness, context status, message
timestamps, skill activity and session management. Native image invocation also
has offline evidence. Native collaboration, automatic/human compaction and human
account/status workflows count without duplicate tools; exposure and freshness
limits still matter. Dynamic thinking control is retired, not ported. Native
human effort controls and launch-time selection remain.

| Capability | Ordinary Codex CLI path | Pi support |
| --- | --- | --- |
| Shared skills and character | Native discovery/instruction surfaces; agent judgment not certified | Existing discovery and surfaces |
| Shell tools / browser UI assets | Shared files, subject to dependencies and sandbox permissions | Existing CLI/assets |
| Account/resource inspection | Native login configuration check and human `/status` account/usage display; refresh where supported, autonomous fresh quota unproven | `codex_account_status` bridge |
| Image generation | Native invocation and workspace copy verified offline; no API-key fallback | `codex_imagegen` bridge with confirmation and saved workspace path |
| Context status | Optional hooks and `context` helper: labelled last-known estimates, raw pressure, input anchor/wall elapsed | `context_status` request-local pressure and task telemetry |
| Compaction | Native automatic compaction/continuation and human `/compact`; no wrapper needed | `context_compact`, including summary-only effort |
| Skill activity | Optional native insertion observer + session-scoped query/control; explicit coverage, separate state | Existing Pi observer/database |
| Collaboration and external exchange | Reused tmux collaboration; native colleague tools optional; shared Node client for external replies | Reused tmux collaboration plus `message_router`, Pi admission and pending context |
| Token awareness | Optional version-pinned hooks/helper above; delayed, coverage-labelled snapshots | Pi branch accounting and request-local annotations |
| Message timestamps | Optional bounded native item-ID/lifecycle-time packets; no body rewriting | Pi historical model-only annotations |
| Session copy/trash | Explicit-store helper: receipt-scoped independent copy or linked fork, bounded OS-trash/native restore; no blanket Pi parity | `pi_session_*` tools |

Choose supported effort at launch. Codex uses
`--model <model> -c 'model_reasoning_effort="medium"'`; Pi uses
`--model <provider/id> --thinking <level>`. Verify effective settings; Pi can
clamp unsupported levels.
Native human Codex `/model` and Pi `/model`/`/thinking` are unchanged. Automata's
retired thinking-control extension and dedicated skill are no longer bundled;
installation does not remove existing copies or reload active sessions. Such
migration requires separate authorization. Other effort parameters remain useful.

Codex 0.159.0's exposed `image_gen.imagegen` can generate directly; do not install
a duplicate Pi-style generator. It returns a native saved path, normally under
`$CODEX_HOME/generated_images/`, not a workspace destination. Use normal filesystem
copying to a checked, non-overwriting workspace path; retain the original if copying
fails rather than regenerating. Availability is model/provider/account/feature
conditional. One-image consent is guidance in Codex, not Pi's bridge confirmation
gate. Offline mock-image success does not prove live entitlement or image quality.

Reuse the existing tmux skills and tool for cross-runtime collaboration. Keep
process ownership, exact receiver identity and acknowledgements explicit; verify
CLI-specific busy/queued-input behavior rather than repeating model collaboration
tests. This preference does not certify live Codex input delivery.

Native collaboration remains optional when actually exposed. In 0.159.0, V1
`send_input` submits work; V2 `send_message` queues without starting an idle target,
while `followup_task` requests a turn. Native waits/completion notifications help
obtain results, but submission or mailbox activity is not completed work. Do not
infer reachability or authority over arbitrary external agents.

For browser requests, use the existing generic Node client in an owned interactive
shell process. The message-router tool ships the task-local recipe at
`docs/node-client.md`; its README links it. It needs a live connection and an
active/resumed agent, not a new polling service. No automatic model wakeup,
durable inbox or Pi delivery modes are promised.

Native automatic compaction already supports continued work; human `/compact`
provides intentional context relief. Preserve material task state rather than
recreating Pi's per-call summary-model settings. The gated native `new_context`
skips summarization and is not a drop-in replacement. Pi preferences stay on Pi.

Account status is distinct from image generation. `codex login status` reports
configured local auth mode, not fresh identity validation or remaining quota; its
API-key output can contain a masked key fragment, so do not echo it into reports.
Human `/status` can display available account/email/plan and usage/reset windows
and request native refresh where supported. Distinguish fresh observations from
stale, missing or unavailable snapshots; context token counts are not quota.
This is useful human-assisted resource inspection, not a proven autonomous fresh
account query. Do not run real account checks without appropriate authority.

A turn-free native RPC fixture returned
rate windows to its controller, but the same account server could not initialize
from the ordinary restricted tool shell because native home writes were required.
That does not establish a working agent account reader or prove every native
account interface unavailable. Native rollout rate-limit observations may be
last-known or absent; do not infer signed-in identity or fresh quota from them.
No account wrapper, credential-copy workaround or permission relaxation is installed.
For the bounded evidence and remaining gaps, see the repository audit
`docs/audits/codex-0.159.0/account-image-native.md`.

Do not call absent Pi tools, attach to an existing Codex daemon, inject history,
trust hooks, or build an adapter as an implicit fallback. Native controls do not
promise Pi summary-model selection, branch token semantics, message projection or
router wakeup/admission. Any future hook/MCP integration needs its own contract,
authorization and validation, not a broad parity claim.

## Verify at the appropriate boundary

After approved installation, check selected files and intended paths. Check native
skill discovery in a fresh authorized Codex session; starting or reloading a
session is separate from placing files. Report discovery independently from
behavioral usability. Do not send model requests merely to validate installation.
A live capability test needs its own allowed effects and prerequisites.

For maintainers, the repository's `docs/audits/codex-0.159.0/proofs.md` gives the
isolated no-network/no-credentials native discovery recipe and explicit limits.
The original audit probe does not use user sessions or a shared daemon. Its
metadata checks do not establish model behavior. The separate
`tests/integration/automata/codex_runtime/sequence_probe.py` and
`verify_sequence_probe.py` prove token acquisition, actual request-body delivery,
inspect/set, compaction exclusion, restart dedup and unknown fork baseline using
an installed fixture and mock provider. `verify_awareness_probe.py` adds actual
native timestamp and context/control/recovery assertions on that fixture.
`activity_probe.py` and `verify_activity_probe.py` prove automatic installed native
skill-insertion recording, discovery/missing-selection exclusion, resume dedup and
recording controls. These tests do not prove live model judgment.
