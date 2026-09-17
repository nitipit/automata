# Automata

Automata packages local-first agent guidance, character components, skills, tools,
and runtime extensions. It keeps agent behavior reusable, inspectable, and bounded
by explicit authorization—not a general-purpose workflow orchestration platform.

See [project goals](goal/main.md) for durable product direction.

Licensed under the [MIT License](LICENSE).

## What is included

- Bundled Automata skills under `src/automata/skills/`
- Packaged character components under `src/automata/character/`
- Bundled repo-local tools under `src/automata/tools/`
- Bundled Pi extensions under `src/automata/extensions/`
- Skill, tool, and Pi extension installers exposed through the `automata` CLI
- Copy, replace, or symlink installation modes

## Usage

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
local collection, and separately authorized draft/send commands. No browser profile, login,
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
Automata's `me.umlab.automata` extension until portable MCP adapters are available.

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

Install the context-status runtime extension:

```bash
uv run automata pi-extension install \
  --target-root ~/.pi/agent/extensions \
  --extension context-status \
  --mode copy
```

`context-status` exposes `/context-status` and the agent-callable
`context_status` tool. It reports runtime context usage, model window, pressure,
elapsed time, the input anchor, and provider-reported model usage. It emits
factual hidden agent signals when meaningful time or pressure observations change.

Install intentional context-compaction guidance and its native Pi extension:

```bash
uv run automata pi-extension install \
  --target-root ~/.pi/agent/extensions \
  --extension context-compaction \
  --mode copy
uv run automata skills install \
  --target-root ~/.agents/skills \
  --skill automata-context-compaction \
  --mode copy
```

`context-compaction` exposes the agent-callable `context_compact` tool. It queues
one intentional request, waits for `agent_settled`, and then calls Pi's native
compaction API. It does not turn context signals into automatic actions or route
built-in commands through tmux or injected messages.

Install the focused image-generation guidance alongside the extension:

```bash
uv run automata skills install \
  --target-root ~/.agents/skills \
  --skill automata-codex-imagegen \
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

`pi-sessions` exposes `pi_session_list` and `pi_session_trash`. Listing uses the
trusted runtime CWD and does not return session paths or conversation content.
Trashing requires a fresh listing receipt and an exact full session ID. The agent
establishes permission from context, asking for clarification or a numbered
selection when needed rather than repeating a clear removal request. There is no
tool-level confirmation dialog. Ownership and inactivity must be established by
the agent; the tool does not detect sessions open in another process. Cleanup
uses recoverable trash only and never falls back to permanent deletion.

For authorized page-to-page, page-to-agent, and agent-to-agent JSON messaging,
see [agent-router](src/automata/tools/agent-router/README.md). Its Pi extension uses
a native `index.ts` bundle; existing single-file extensions remain supported.

Use `--source-root <path>` to install skills, tools, or Pi extensions from a different
local source root.

Modes:

- `copy`: destination directories must not exist.
- `replace`: remove existing destination directories first, then copy.
- `symlink`: destination directories must not exist; create symlinks to the source.

Copy and replace installs honor optional per-tool `.automataignore` declarations so generated
working trees are not installed. Symlink mode intentionally remains a transparent development
view of the source, including any ignored local output present there.

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
python src/automata/skills/operations/automata-adaptive-ui/scripts/build.py \
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

Skills are grouped under the source-only categories `core`, `communication`,
`development`, `skill-ops`, and `operations`. The installer discovers `SKILL.md` files
recursively below `--source-root` and installs each skill into the flat runtime namespace
by its skill name; source categories are not exposed at runtime.
