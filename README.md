# Automata

Automata packages local-first agent guidance, character components, skills, tools,
and runtime extensions. It keeps agent behavior reusable, inspectable, and bounded
by explicit authorization—not a general-purpose workflow orchestration platform.

Licensed under the [MIT License](LICENSE).

## What is included

- All bundled skills under `src/automata/skills/bundled/`
- Packaged character components under `src/automata/character/`
- Bundled repo-local tools under `src/automata/tools/`
- Bundled Pi extensions under `src/automata/runtimes/pi/extensions/`
- Skill, tool, and Pi extension installers exposed through the `automata` CLI
- Copy, replace, or symlink installation modes

## Source layout and runtime boundaries

```text
src/automata/
├── character/              # Shared identity and behavior
├── tools/                  # Shared shell-invoked CLI tools
├── apps/                   # Maintained application source and canonical skills
├── runtimes/
│   ├── pi/
│   │   └── extensions/     # Pi APIs, event handlers, and session integrations
│   └── codex/             # Optional native CLI awareness/session helpers
├── install/                # Asset discovery and installation
└── plugin/                 # Selected-asset package export
```

Maintain application source under `src/automata/apps/<app-name>/` and generated
builds or runtime data under `.agents/var/apps/<app-name>/`, outside source control.
Each application determines its own internal layout.

Portable skills stay brand-neutral. Runtime-specific skills explicitly identify
the extension or native interface they require; installation does not expose it.
Pi retains context compaction/status, session tools, the Codex
image-generation bridge, skill recording and the message-router session adapter.
The router CLI stays shared under `tools/message-router/`. A model/provider name
does not determine the host runtime: `codex-bridge` is a Pi extension, not a Codex
integration.

Native Codex CLI can use the same skill catalog, character content and shell tools.
See [Codex setup and support](src/automata/runtimes/codex/setup.md)
for direct-install commands, instruction surfaces, optional plugin packaging and
explicit remaining gaps. Reuse tmux collaboration across both runtimes; native
collaboration is optional. Automatic/human compaction, image generation and human
account/status inspection count as useful support;
matching Pi tool names is not the goal. External browser exchange can use the
[existing Node client recipe](src/automata/tools/message-router/docs/node-client.md)
from an owned active shell process, with permitted loopback and private grants.
No automatic model wakeup or autonomous fresh quota query is promised.
No wrapper or custom host is required. Optional
`automata codex install --target-root <assets> --state-root <state>` packages the
[Codex awareness/skill-activity hooks and session controls](src/automata/runtimes/codex/README.md); config/trust
activation and current-session transcript reading require explicit consent.
Native 0.159.0 mock-provider tests prove sequence-linked token acquisition,
context estimates, native item timestamps, automatic selected-skill insertion
recording, delayed delivery, controls and scoped recovery—not live model judgment
or identical Pi branch semantics. Explicit session controls separately support
scoped metadata receipts, verified independent materialized copies (not linked
native forks), and bounded genuine OS-trash/native restore. They require selected
store/IDs, established inactivity and their own authorization; no automatic hook
mutation or global activation. The
[audit](docs/audits/codex-0.159.0/README.md) and
[token slice proof](docs/audits/codex-0.159.0/token-sequence-port.md) and
[context/timestamp proof](docs/audits/codex-0.159.0/context-timestamps-port.md) and
[skill-activity proof](docs/audits/codex-0.159.0/skill-activity-port.md) and
[session-management proof](docs/audits/codex-0.159.0/session-management-port.md) separate
evidence from remaining runtime work.

Default skill installation and selected-skill plugin export use the single canonical
catalog at `src/automata/skills/bundled/`. Duplicate names are errors,
not implicit overrides. An explicit custom skill source is exclusive; it never
falls back to bundled skills.

This is source organization, not installation or data migration. The extension-bound
skills are now `automata-pi-context-compaction`, `automata-pi-context-status` and
`automata-pi-skill-activity`; portable image guidance is `automata-imagegen`.
Select matching runtime-specific skills explicitly; full-catalog installation does
not filter by host. Installers do not remove old skill names. Retire old copies
only during an authorized sync, after reviewing local changes, to avoid duplicate
activation guidance. Extension destinations, credentials and operational state
remain unchanged, including existing `automata-context-compaction` preference
paths, skill-activity databases and `.agents/var/tools/agent-router` router state.
Historical audits retain the names and evidence from their original checkpoints.

## Design principles

These principles guide Automata’s development without replacing the user’s task
objectives.

- Prefer simple, inspectable files and local workflows. Keep installation,
  linking, and durable state choices explicit, reversible, and understandable
  from the workspace.
- Keep guidance focused and easy to use at startup and handoff, with clear
  activation, boundaries, and enough direction for a useful first action.
  Generalize reusable behavior rather than encoding one-off session details;
  see [skill design](src/automata/skills/bundled/automata-skill-design/SKILL.md).
- Make consequential actions controllable across digital and physical
  environments. Expose permissions, confirmation boundaries, observable outcomes,
  and practical recovery paths proportionate to the impact.
- When using web interfaces for human-agent collaboration, support both
  session-based and browser-first work. Preserve continuity, make outcomes
  visible, and keep human direction and authorization explicit.

## Capability research

`automata-capability-research` guides assessments of capabilities that could improve
Automata, including readiness for unfamiliar problems—not only fixes for existing
pain points. It distinguishes available knowledge, operational readiness, and
permission to use a capability. It does not redirect ordinary user-task research
into Automata development or authorize adoption.

Its purpose and assessment guidance live directly in
[`SKILL.md`](src/automata/skills/bundled/automata-capability-research/SKILL.md),
without a separate goal document or runtime notes.

## Model selection

[`automata-model-selection`](src/automata/skills/bundled/automata-model-selection/SKILL.md)
helps choose AI models for tasks, plans and solo/team assignments using existing
comparative knowledge and approved preferences. It recommends a fit and tradeoff;
teamwork design owns assignments and planning owns decomposition. Research fills
only decision-relevant evidence gaps, not a mandatory phase for every choice.
User-approved model preferences stay separate from research findings; new evidence
does not authorize a model switch or expand an allowed list.

Ask, for example, "Which models should we use in this work plan?", "Design a team
and recommend models for its assignments", or "Is this new model worth considering?"
Reusable notes and preferences remain under
`~/.agents/var/skills/automata-model-research/`, with project-specific observations
and explicit overrides under `.agents/var/skills/automata-model-research/`.
These legacy data paths remain canonical; the rename does not migrate data.
Installation does not create a model catalog, preferences, or runtime configuration.
Retire the old `automata-model-research` installed skill during an authorized sync,
without deleting its operational data; installers do not remove old names.

## Runtime environment discovery

[`automata-runtime-environment`](src/automata/skills/bundled/automata-runtime-environment/SKILL.md)
helps an agent discover only the runtime and execution-environment facts needed
for its task. It supports unfamiliar harnesses through targeted evidence and
retains useful verified inspection recipes outside the package, revalidating
changeable assumptions on later use. Active observations, configured defaults,
and user preferences remain distinct; inspection does not authorize changes.

This replaces `automata-runtime-status` and retains active provider/model/thinking
verification within the broader scope. Installers do not automatically remove old
installed names; retire the old skill package during an authorized sync without
removing operational data. Existing installations are not migrated automatically.

## Git worktrees

[`automata-git-worktree`](src/automata/skills/bundled/automata-git-worktree/SKILL.md)
guides task-owned checkout isolation, placement, reuse, integration and safe
retirement. It follows established location conventions, checks whether a nested
task workspace is safe, and retains useful setup recipes outside the package.
Worktrees share Git state and are not security sandboxes. Creation does not grant
permission to publish changes or delete work; cleanup accounts for active users,
ignored files and unpreserved commits. Ordinary coding needs no worktree ceremony.

## Storage

[`automata-storage`](src/automata/skills/bundled/automata-storage/SKILL.md) guides
placement, ownership, retention, and cleanup of capability-owned operational data
under `.agents/var/skills/`, `.agents/var/tools/`, and `.agents/var/apps/`.

[`automata-task-space`](src/automata/skills/bundled/automata-task-space/SKILL.md) guides
task workspace reuse, organization, continuation, promotion, and safe cleanup.
It retains `.agents/var/workspace/<task-name>/` as an optional repository-local
fallback. Neither skill requires moving existing data.

`automata-storage` replaces the `automata-agent-data` skill name. Installers do not automatically
remove old installed names; retire the old skill package during an authorized sync,
without removing its operational data.

## Usage

Shared installation examples below apply to Pi and Codex CLI. Sections that
install Pi extensions or expose Pi tools remain Pi-only; they do not register
Codex tools. Choose either direct skill installation or plugin exposure for each
skill rather than duplicating it across roots/mechanisms. Codex can retain
same-name skills from multiple roots; do not assume nearest-wins precedence.

List packaged character components:

```bash
uv run automata character list
```

Compose character instructions for another agent to read:

```bash
uv run automata character compose \
  --personality automata \
  --language thai \
  --behavior co-pilot
```

`language/base.md` and `behavior/base.md` are included automatically before selected
components. The command prints Markdown to stdout, including discovery guidance for the
default repository-local instruction directory, and does not edit `AGENTS.md` files.

Generate an `AGENTS.md`:

```bash
uv run automata character compose \
  --personality automata \
  --language thai \
  --behavior co-pilot \
  > AGENTS.md
```

Use `--agents-md <path>` to override the additional-instruction directory.

Install one bundled skill:

```bash
uv run automata skills install \
  --target-root .agents/skills \
  --skill automata-plan \
  --mode copy
```

Install selected skills with repeatable or comma-separated `--skill` values:

```bash
uv run automata skills install \
  --target-root .agents/skills \
  --skill automata-agents-md,automata-delegation \
  --mode copy
```

Install all bundled skills:

```bash
uv run automata skills install \
  --target-root .agents/skills \
  --mode copy
```

Install the bundled timer tool into a repository:

```bash
uv run automata tools install \
  --target-root .agents/tools \
  --tool timer \
  --mode copy
```

Install the tmux message helper for owned agent panes:

```bash
uv run automata tools install \
  --target-root .agents/tools \
  --tool tmux-message \
  --mode copy
```

Install the LINE Chrome skill and its companion tool:

```bash
uv run automata skills install --target-root .agents/skills --skill automata-line-use --mode copy
uv run automata tools install --target-root .agents/tools --tool line --mode copy
uv run --script .agents/tools/line/line.py --help
```

LINE use currently supports Linux with an explicitly isolated Chrome profile and the user's
own LINE login. It provides structured reads, per-consumer reading checkpoints, recoverable
local collection, and separately authorized draft/send commands. Sticker commands
`sticker-catalog` and `prepare-sticker` inspect metadata without clicking sticker tiles;
`send` consumes the recipient/sticker-bound token before one intentional click.
Only observed, owned, non-effect sticker identities are supported; unfamiliar UI or
asset shapes fail closed. Uncertain sends hold the sticker receipt for reconciliation,
and operation-owned picker cleanup is reported separately from dispatch.
No browser profile, login,
chat transcript, runtime state or timer is installed. Paths resolve from the calling workspace;
`AUTOMATA_LINE_PROFILE` and `AUTOMATA_LINE_TIMEZONE` select an isolated profile and timezone
(default UTC). The CLI declares its optional Playwright, Cyclopts and Dictify dependencies;
these are not added to Automata's core dependencies. Use `uv run --offline --with playwright
--with dictify pytest tests/unit/automata/tools/line_reading_test.py
tests/integration/automata/tools/line` for the fixture and installed-CLI tests with cached
optional dependencies. No real messages are sent by those tests.

Adaptive UI is a self-contained skill with maintained TypeScript, schemas, build inputs,
and examples. Install it without a prebuilt browser bundle, then build its shared runtime library:

```bash
uv run automata skills install \
  --target-root .agents/skills \
  --skill automata-adaptive-ui \
  --mode copy
python .agents/skills/automata-adaptive-ui/scripts/build.py \
  --runtime-root .agents/var/skills/automata-adaptive-ui
```

Installation stays copy-only. The explicit build needs Python >=3.12, Deno, cached locked
dependencies, and Node >=20.19; it never fetches dependencies silently. It builds in a disposable
runtime workspace and atomically updates `lib/adaptive-ui.js` without writing into maintained
or installed skill source. A failed build leaves the existing library intact. Add `--check` to
compare freshness without replacement, or `--validate` for Deno type checks, tests, and lint.

The default skill-owned website root is resolved against the agent's working CWD,
not the installed skill location (an explicit runtime root may override it):

```text
.agents/var/skills/automata-adaptive-ui/
├── lib/adaptive-ui.js
└── sessions/<name>/
```

There is no separate Adaptive UI tool installation. One loopback server serves this website
root; `/sessions/<name>/` is a subpage with its own files and assets, not a separate deployment.
Pages import `/lib/adaptive-ui.js` directly—no bundle copies or mandatory `public/` directory.
Normal rendering treats the shared library as read-only; rebuilding it affects what sessions
load on their next reload. Keep profiles, private records, secrets, and build workspaces outside
the served tree. Deno and Node are build prerequisites, not display prerequisites.

The browser asset exports Arrow primitives for instance-local reactive state inside registered
`Base` components, while Adapter owns component CSS. Automatic and agent-triggered reloads are
full reloads, not hot-state preservation. Use private source copies and separate website roots
for isolated library experiments;
promote reusable components into the skill's canonical source only after confirmation.
Existing installations and sessions are not removed or migrated automatically. Release
distribution remains deferred.

Adaptive UI currently composes one-way browser displays from the agent's perspective. Arrow events
may update browser-local state, but buttons and forms do not return structured user results to the
agent; interaction transport remains a separate future capability.

Export a selected group of skills and Automata-specific tools as an Agent Plugin:

```bash
uv run automata plugin export \
  --name automata-core \
  --profile core \
  --output examples/plugins/automata-core
```

Profiles provide a starting selection; repeat `--skill` or `--tool` to add explicit assets.
Skills are exported to the standard `skills/` directory. Selected tools are packaged under
Automata's `me.umlab.automata` metadata namespace and remain shell-invoked CLI tools;
export does not register them with an agent runtime.

### Pi integrations

The remaining extension examples in this section are for Pi, including when Pi
uses a Codex model. They are not native Codex CLI setup steps.

Install the Codex account-status extension globally for all Pi sessions:

```bash
uv run automata pi-extension install \
  --target-root ~/.pi/agent/extensions \
  --extension codex-bridge \
  --mode copy
```

`codex-bridge` uses the existing Codex CLI login and exposes `/codex-status` and
an agent-callable `codex_account_status` tool. It also exposes
`codex_imagegen`, which delegates one explicitly authorized or confirmed
raster-image generation to the native Codex image-generation capability and
copies the saved image into the workspace. It does not expose a general-purpose
Codex task runner.

Install the skill-load recorder globally, with its skill in repository and global catalogs:

```bash
uv run automata pi-extension install \
  --target-root ~/.pi/agent/extensions --extension skill-activity --mode copy
uv run automata skills install \
  --target-root .agents/skills --skill automata-pi-skill-activity --mode copy
uv run automata skills install \
  --target-root ~/.agents/skills --skill automata-pi-skill-activity --mode copy
uv run --no-project --script ~/.pi/agent/extensions/skill-activity/store.py --help
```

After `/reload` or a fresh session, `skill-activity` observes complete `SKILL.md`
reads and records metadata in global ShelfDB storage at
`~/.agents/var/tools/skill-activity/db`, validated by Dictify. Each record retains
its project path; `list --project /absolute/project/path` scopes queries before
applying the limit. Existing project-local records are not migrated automatically.
The bundled CLI provides only `record` and `list`; it is not a general database API.
No instruction bodies or conversations are stored. Dependency preparation may
need downloads; the observer itself runs offline. See the
[skill-activity skill](src/automata/skills/bundled/automata-pi-skill-activity/SKILL.md)
for discoverable query guidance, the data contract, and coverage limits.

Install the context-status runtime extension:

```bash
uv run automata pi-extension install \
  --target-root ~/.pi/agent/extensions \
  --extension context-status \
  --mode copy
```

`context-status` exposes `/context-status` and the agent-callable
`context_status` tool. It reports runtime context usage, model window, pressure,
elapsed time, the input anchor, and provider-reported model usage. Temporary
pressure reminders reach the next model request at 75%, 80%, 85%, 90%, and 95%,
with a moderate observation at 50%. They are deduplicated across user inputs and
rearmed after successful compaction or context identity changes. Elapsed-time
observations remain queued after the run settles. Signals do not run compaction.

Stable conversational times are owned by the separate `message-timestamps`
extension, not context-status. It annotates model-facing user messages, assistant
messages containing visible text, and routed `browser-context` messages with their
original Pi timestamp in UTC. Tool-only/thinking-only messages, tool results,
system messages and internal events are untouched. Stored text is not rewritten;
annotations are deterministic across requests, reloads and timezone changes.
Missing timestamps remain unknown. Retained post-compaction messages keep their
original dates; summaries do not receive invented historical dates. Pi may build
compaction input without this context hook, so summaries are not guaranteed to
retain annotations. Assistant timestamps describe creation, not exact completion,
the current clock, or active-work duration. Conversation intervals include pauses;
do not infer active work from timestamps or token usage.

When explicitly authorized to activate this change, install **both** the new
extension and updated context-status, then reload Pi or start a new session:

```bash
uv run automata pi-extension install \
  --target-root ~/.pi/agent/extensions \
  --extension message-timestamps --extension context-status --mode replace
```

Updating context-status removes its old changing request-clock injection. Loading
message-timestamps alongside an *old* installed context-status leaves both behaviors
active. No current-clock tool or extra model turns are added. Use an explicit clock
check when current time matters. Stable prefixes are tested offline; provider cache
savings and hidden/private model reasoning visibility are not claimed.

### Token usage landmarks

The separate `token-awareness` extension adds stable, model-only usage landmarks.
It does not replace context-status's input-anchored telemetry, elapsed-time signals,
pressure reminders, or compaction behavior. It has **no elapsed-time trigger** and
adds no model requests. Message timestamps retain their per-message behavior.

```bash
uv run automata pi-extension install \
  --target-root ~/.pi/agent/extensions --extension token-awareness --mode copy
```

Activation/reload requires separate authorization. The `token_awareness` tool can
`inspect` the active branch or `set` a session-local threshold (integer 1 through
1,000,000,000; default 100,000). Counted tokens are Pi-normalized uncached `input` +
`output` + `cacheWrite`; `cacheRead` is reported but excluded from the trigger.
Cache writes and reasoning subsets are not counted twice. A crossed threshold
creates one landmark with the actual delta, even after a multi-threshold jump.
Changing the threshold does not reset accrued usage or revise old landmarks.
Lowering it below accrued usage creates one landmark at the next turn-end or
context boundary; it does not wake the model.

Landmarks report per-category delta and cumulative **main-assistant response**
usage on the active branch, including tool-call-only rounds. Nested tool model
calls, compaction/branch-summary model calls, cache warming, and abandoned branches
are excluded. Missing/invalid usage is counted as unknown, not zero. Valid zero
records are retained and flagged separately: Pi can initialize missing provider
telemetry to zero, so the extension cannot prove whether such a record was a true
zero measurement. Totals are not full-session billing totals or active-work timers.

Immutable metadata lives in Pi custom entries, separate from stored conversation
text. Each request replays model-facing annotations at branch positions; compacted
or omitted anchors move to the next surviving context message. Raw branch ancestry
preserves totals across compaction and reload, without counting summary usage.
Old landmarks intentionally remain after compaction; they are not recreated with
new dates. Corrupt or inconsistent landmark metadata is ignored, never used as an
accounting baseline. Replay scans the active ancestry and projected messages with
linear ordered matching; it does not scan abandoned branches.
Forks inherit their selected ancestry and settings; old landmarks retain original
session/branch IDs, while new ones identify the child session. Tree navigation
restores that branch's threshold and totals, never future-branch state. Loading
into existing history may create one catch-up landmark with today's creation
metadata, not invented historical annotation dates. No global settings are changed.

The canonical time-awareness skill is retired; installed copies are not removed.
Timestamp limitations remain documented above. Scheduling remains owned by the
unchanged timer capability.

Install intentional context-compaction guidance and its native Pi extension:

```bash
uv run automata pi-extension install \
  --target-root ~/.pi/agent/extensions \
  --extension context-compaction \
  --mode copy
uv run automata skills install \
  --target-root ~/.agents/skills \
  --skill automata-pi-context-compaction \
  --mode copy
```

`context-compaction` exposes the agent-callable `context_compact` tool. It queues
one intentional request, waits for `agent_settled`, and then calls Pi's native
compaction API. It does not turn context signals into automatic actions or route
built-in commands through tmux or injected messages.

Choose the approved model and supported effort at launch, using the runtime's
own options: Pi `--model <provider/id> --thinking <level>`; Codex
`--model <model> -c 'model_reasoning_effort="medium"'`. Pi can clamp a requested
level to the model's capabilities: verify the effective startup setting rather
than treating the command line as proof. Native human Pi `/model` and `/thinking`,
and Codex `/model`, remain available.

Automata's dynamic `thinking_control` tool and dedicated skill are retired; its
Codex port is stopped. This does not remove compaction-specific effort, imagegen
settings or other independent effort parameters. Source installers no longer
ship the retired assets but do not uninstall existing user copies or change
active sessions. Any installed removal/reload requires separate authorization.
See the [retirement decision](docs/audits/codex-0.159.0/thinking-control-retirement.md)
for evidence, limits and the eight retained capabilities.

Install the focused image-generation guidance alongside the extension:

```bash
uv run automata skills install \
  --target-root ~/.agents/skills \
  --skill automata-imagegen \
  --mode copy
```

Install safe exact-CWD Pi session discovery and cleanup:

```bash
uv run automata pi-extension install \
  --target-root ~/.pi/agent/extensions \
  --extension pi-sessions \
  --mode copy
uv run automata skills install \
  --target-root ~/.agents/skills \
  --skill automata-pi-sessions \
  --mode copy
```

`pi-sessions` exposes `pi_session_list`, `pi_session_copy` and `pi_session_trash`.
Listing defaults to the trusted runtime CWD and its active session store. Optional
`cwd` selects another exact directory; `scope: "global"` searches across projects.
These broader scopes use Pi's default store, not custom stores or target project
configuration. Results contain recorded CWD and directory status but omit session-file
paths and conversation content. `directoryStatus: "missing"` identifies review
candidates, not permission to delete; inaccessible paths are `unknown`.

Pages contain at most 100 sessions (`limit` may reduce this). Follow `nextCursor` by
passing `cursor` alone; each page supersedes previous receipts. Duplicate IDs are
non-selectable, and changed files are omitted from the snapshot. A separate
`copyReceipt` permits an explicit copy request with selected `sessionIds` and an
existing `targetCwd`.
Copies get new IDs and source provenance, preserve originals, and use default
session storage at the destination. They do not copy project files or rewrite
historical paths. Partial failures may leave destination copies; inspect reported
IDs before retrying. Source sessions must be inactive; the current session is rejected.

All listing scopes issue a separate trash receipt bound to the listed source
identities. Trashing requires that fresh receipt and exact full session IDs; it never
accepts arbitrary session-file paths. Copying and listing do not grant deletion
permission. Directory status and source identity are rechecked before mutation. The agent
establishes permission from context, asking for clarification or a numbered
selection when needed rather than repeating a clear removal request. There is no
tool-level confirmation dialog. Ownership and inactivity must be established by
the agent; the tool does not detect sessions open in another process. Cleanup
uses recoverable trash only and never falls back to permanent deletion.

For authorized page-to-page, page-to-agent, and agent-to-agent JSON messaging,
see [message-router](src/automata/tools/message-router/README.md), with Pi tool
`message_router` and skill `automata-message-router`. Its Pi extension uses a native
`index.ts` bundle; existing single-file extensions remain supported. This replaces
the `agent-router` package name, not its stored data. Retire the old extension during
an authorized sync rather than loading both; see the router's migration notes.

Use `--source-root <path>` to install skills, tools, or Pi extensions from a different
local source root.

Modes:

- `copy`: destination directories must not exist.
- `replace`: remove existing destination directories first, then copy.
- `symlink`: destination directories must not exist; create symlinks to the source.

Tool copy and replace installs exclude Python bytecode artifacts (`__pycache__/`,
`*.pyc`, `*.pyo`) by default; no per-tool ignore file is needed. `.gitignore`
controls Git tracking, not installer file selection. Symlink mode intentionally
remains a transparent development view of the source, including local output.

Tools may alternatively declare entry and file selection through `deno.json` `exports` and
`publish.include`; the config itself is always included. Legacy `.automataignore` handling
remains available when no Deno include list is present. Adaptive UI is packaged with its skill
and does not use this tool-installation mechanism.

The source installer reads strict-JSON `deno.json`, supporting a single literal `./` path for
`exports` and literal relative file/directory paths in `publish.include`. It checks every
selected tool before changing destinations, including in symlink mode; a missing entry reports
a build-first error. With an include list declared, the entry must also be selected. Symlinks
still expose the whole source tree. This uses standard metadata for local copies, not a Deno
publish implementation: JSONC, glob patterns, export maps and nonempty `publish.exclude` lists
are unsupported and fail explicitly. No Deno/npm command or lifecycle script runs during
installation. Release distribution remains deferred.

## Development

Install dependencies with uv:

```bash
uv sync
```

Run tests directly from a clean checkout; no generated browser asset is required in source.
Adaptive UI build integration tests use disposable skill installations and runtime roots,
with Deno, Node, and cached dependencies (no implicit fetching):

```bash
uv run pytest
```

These checks validate software and packaging, not agent judgment. See
[the testing guide](tests/README.md) for the test layout, instruction review, and
separate whole-agent behavioral evaluation.

For an explicit developer build and frontend validation, choose a runtime root outside source:

```bash
python src/automata/skills/bundled/automata-adaptive-ui/scripts/build.py \
  --runtime-root .agents/var/skills/automata-adaptive-ui --validate
```

Run lint checks:

```bash
uv run ruff check .
```

Run type checks:

```bash
uv run ty check \
  src/automata/*.py \
  src/automata/tools/timer/timer.py \
  src/automata/tools/tmux-message/tmux_message.py
```

## Skill package shape

Each skill lives in its own directory and should include a `SKILL.md` file:

```markdown
---
name: automata-example
description: Use when an agent needs the example workflow.
---

# Automata Example
```

All bundled skills live in the flat canonical catalog at
`src/automata/skills/bundled/`, including skills with Pi-specific usage
requirements. Tools and Pi extensions retain their separate owner locations. The
installer discovers `SKILL.md` files in the catalog and installs each directory with
its supporting assets. An explicit `--source-root` selects only that directory.
