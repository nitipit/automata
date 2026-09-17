---
name: automata-toolsmith
description: Use when creating, improving, reviewing, or maintaining small repo-local tools that reduce repeated friction, token usage, risk, or context overhead.
---

# Automata Toolsmith

Turn repeated mechanical friction into small, inspectable, easy-to-run tools.
Prefer tools that help both agents and humans work with less context, fewer
manual steps, and clearer validation.

Create a tool only when repeated mechanics, clear input/output contracts, or reduced
operational risk justify maintenance. One-off actions are often better as direct
commands; do not automate unclear judgment merely because a tool could exist.

## Creation Permission

By default, propose tools before creating or modifying them. Tool creation can
add files, dependencies, maintenance burden, and system state, so confirm the
management approach first.

When the user explicitly requests autonomous work, the agent may create small
local tools without per-tool confirmation only after the user has confirmed a
tool-management contract covering stack, location, dependencies, generated
artifacts, cleanup, and forbidden actions.

Even in autonomous mode, ask before global installs, system package changes,
heavy dependencies, long compilation, unmanaged background processes, writing
outside approved locations, or automating risky external side effects.

## Tool Shape

Prefer CLI-first tools. A good tool should be easy for agents and humans to run,
accept explicit arguments, print useful stdout/stderr, return meaningful exit
codes, and write outputs to predictable locations.

Keep tool output focused on results, observable state, provenance, and actionable
errors. Avoid redundant labels and repeated behavioral instructions. Put stable
usage guidance in help, tool descriptions, or the relevant skill. Preserve
information needed to interpret results safely, including source and correlation
identifiers.

Prefer small composable commands over large frameworks or hidden agent-only
interfaces. Library modules are fine underneath, but the public interface should
usually be a CLI.

Good CLI traits:

- clear command name and `--help`
- explicit inputs and output paths
- useful exit codes
- readable default output, with JSON only when useful
- predictable cache, temp, log, and artifact locations
- `status`, `stop`, or `cleanup` when the tool manages state

## Operability

Prefer tools that run quickly, install locally, and leave no unmanaged garbage.
Avoid long compilation, global installation, hidden background processes, or
uncontrolled writes for routine agent tools.

Good defaults:

- Python: `uv`, project-local `.venv`, `uv run ...`
- JavaScript/TypeScript: `pnpm`, project-local dependencies, `pnpm exec ...`
- Deno: single-file tools with explicit permissions when that is simpler
- Shell: tiny glue only; switch to a real language when parsing, state, or
  retries become non-trivial

Use compiled stacks only when performance, portability, or distribution clearly
justifies the build cost.

## Default Stacks

Follow the repository's existing tool conventions first. If none are clear, use
these defaults.

For Python CLI tools:

- prefer `uv` for runtime and dependency management
- use `cyclopts` for command definitions and self-documenting help unless a confirmed runtime
  constraint prohibits dependencies
- use `dictify` when structured results, config, or state serialization benefits
  from it
- keep tiny tools on the standard library when extra dependencies do not reduce
  complexity

For JavaScript/TypeScript CLI tools:

- prefer `pnpm` for package and script execution
- prefer `tsx` for no-build TypeScript execution
- use `node:util.parseArgs` for tiny scripts
- use `commander` for normal local CLIs
- use `zod` only when runtime validation materially improves safety

For Deno CLI tools:

- prefer a pinned Cliffy release for durable, self-documenting CLIs
- use manual `Deno.args` parsing only for tiny dependency-free or bootstrap scripts
- keep dependency fetching explicit with `deno cache`, then use `deno run --cached-only`
- document recovery when Deno is missing or required dependencies are not cached
- do not install Deno or fetch dependencies silently

Use schema validation for structured, persisted, safety-sensitive, or externally
exposed inputs. For simple scalar CLI flags, rely on the CLI parser and explicit
checks.

## Tool Location

Choose placement from the tool's purpose, intended owner, and project conventions.
Toolsmith develops tools; it does not automatically own the tools it creates.
Distinguish three concerns, not three mandatory directories:

- **Source:** maintained code in the project's source or development-tool layout.
  A helper shipped with one skill may live in that skill's `scripts/`.
- **Installed copy:** the executable distribution surface, when needed. Change
  maintained source and reinstall rather than patching installed copies.
- **Runtime state:** mutable logs, caches, and other operational data under the
  applicable owner-scoped data convention, separate from maintained source and
  installed code.

When reusable setup knowledge helps, separate it from live process handles and
provide inspectable checks for changed prerequisites. Do not treat a saved endpoint
as current identity or repeat discovery that verified configuration already resolves.

Stateless tools need no state directory; project-only tools may run directly from
source without an installed copy. Use an approved disposable location for temporary
helpers. Confirm unclear locations before writing; do not move existing files or
create unused directories merely to match this separation.

## Agent-Facing Automata Tools

For packaged Automata tools, `src/automata/tools/<name>/` holds maintained source,
`.agents/tools/<name>/` holds installed copies, and `.agents/var/tools/<name>/`
holds runtime state when needed, unless an explicit data convention overrides it.
These are Automata conventions, not a required layout for other projects.

When a skill owns usage judgment, it maps the installed `.agents/tools/...` entry
in `metadata.automata-tools` and documents usage and missing-tool recovery. Runtime
skill instructions use installed entries, not package source paths. A stand-alone
tool may instead provide sufficient direct CLI documentation; do not invent a
wrapper skill merely to give the tool an owner.

## Documentation

Document enough for the next human or agent to run and remove the tool.

- Tiny one-off tools need `--help` or a short top comment.
- Every subcommand and non-obvious option should have meaningful help describing its purpose,
  expected value, important defaults, and effects. Root and command `--help` should let an
  agent operate the tool correctly without reading its implementation.
- Durable CLIs should make root and command `--help` sufficient for operation, including
  important defaults, state and artifact paths, effects, safety boundaries, and cleanup.
- Prefer executable discovery commands for schemas or machine-readable contracts that do not
  fit clearly in help text.
- Do not add a tool-level usage README when CLI help owns the same information. Keep separate
  files only for concerns such as licenses, provenance, or substantial non-CLI architecture.
- Tools that manage background processes or persistent state need a clear
  `status`, `stop`, and cleanup story in their CLI help.

## Validation

Validate new tools before relying on them. At minimum, run `--help` and one
representative command. For durable or risky tools, also test failure behavior
and add small automated tests when they reduce future risk.

Do not overbuild test suites for one-off helpers. Prefer smoke checks and
real-task validation unless the tool is becoming durable project infrastructure.

## Boundaries

- Do not create tools for unclear judgment problems.
- Do not add dependencies, lockfiles, background processes, or generated
  artifacts without need or confirmation.
- Do not prefer framework-building over small purpose-built commands.
- Do not hide important state behind automation when visible inspection is safer.
- Do not make global or system-level changes unless the user explicitly approves
  them.
- Keep agent-facing tools discoverable through an applicable skill mapping or sufficient
  direct CLI documentation; tool creation does not transfer ownership to Toolsmith.
