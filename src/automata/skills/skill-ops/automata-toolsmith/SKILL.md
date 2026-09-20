---
name: automata-toolsmith
description: Use when creating, improving, reviewing, or maintaining small repo-local tools that reduce repeated friction, token usage, risk, or context overhead.
---

# Automata Toolsmith

Turn repeated mechanical friction into small, inspectable tools that agents and
humans can operate with less context. Create a tool only when repeated work, clear
input/output contracts, or reduced operational risk justify its maintenance.
Prefer direct commands for one-off work; do not automate unclear judgment or build
a framework where a small composable command is sufficient.

## Authority and repair

Propose creation or modification before acting unless already approved. Autonomous
work permits small local tools without per-tool confirmation only within a confirmed
management contract covering stack, location, dependencies, generated artifacts,
cleanup, and forbidden actions. Ordinary implementation choices within an approved
repair need no repeated proposal.

Ask before global installs, system changes, heavy dependencies, long compilation,
unmanaged background processes, writes outside approved locations, or risky external
effects. Do not add dependencies, lockfiles, processes, or artifacts without need and
applicable authority.

A tool failure is evidence to investigate, not permission to modify it. Distinguish
a defect from incorrect invocation or missing setup. Separate an authorized task
workaround from a reusable repair: repair maintained source only within scope,
preserve permission checks, and do not silently deploy the fix elsewhere. A working
alternative does not mean the original tool is repaired; disclose what remains broken.

## Interface and documentation

Prefer CLI-first, composable commands; library modules may support them. Accept
explicit inputs and output paths, return meaningful exit codes, and provide useful
stdout/stderr. Use readable output by default and JSON when useful. Report results,
observable state, actionable errors, and provenance or correlation identifiers needed
for safe interpretation—not redundant labels or repeated behavioral instructions.
Do not hide important state when direct inspection is safer.

Keep operation discoverable without reading implementation:

- Tiny one-off helpers need `--help` or a short top comment.
- Durable CLIs need root/subcommand help explaining purpose, non-obvious options,
  expected values, defaults, effects, state/artifact paths, safety limits, and cleanup.
- Use executable discovery for schemas or contracts too large for clear help text.
- Tools managing state or processes need a clear `status`, `stop`, and cleanup story.
- Keep usage in CLI help, tool descriptions, or the owning skill. Do not duplicate
  it in a tool-level README; separate docs may cover licenses, provenance, or
  substantial non-CLI architecture.

## Implementation choices

Follow project conventions first. Prefer quick-running local tools, predictable
cache/temp/log/artifact locations, and controlled writes. Avoid hidden processes
and unmanaged leftovers. Use compiled stacks only when performance, portability,
or distribution justify their build cost. Keep shell to tiny glue; use a real
language when parsing, state, or retries become non-trivial.

When choosing a stack without established conventions, consult
[Stack defaults](references/stacks.md). These are defaults, not permission to
install runtimes or fetch dependencies. Use schema validation for structured,
persisted, safety-sensitive, or externally exposed inputs; ordinary scalar CLI
flags usually need only parser validation and explicit checks.

## Ownership and placement

Place tools by purpose, intended owner, and project conventions. Toolsmith develops
tools; it does not automatically own them. Separate these concerns without imposing
three mandatory directories:

- **Source:** maintained project code; a skill-specific helper may live in its
  `scripts/` directory. Make repairs here, then deploy only with authority.
- **Installed copy:** an optional distribution surface, not the repair source.
- **Runtime state:** mutable logs, caches, and operational data in the applicable
  owner-scoped location, separate from source and installed code.

Stateless tools need no state directory; project tools may run directly from source.
Use approved disposable locations for temporary helpers. Resolve unclear placement
before writing; do not move files or create unused directories to fit this model.

Retain useful verified setup knowledge separately from transient process handles.
Check changed prerequisites and live identity before reuse; a saved endpoint is not
ownership evidence. Reuse valid knowledge rather than repeating discovery.

For packaged Automata tools, default to `src/automata/tools/<name>/` for source,
`.agents/tools/<name>/` for installed copies, and `.agents/var/tools/<name>/` for
needed runtime state unless an explicit convention overrides it. These paths are
Automata conventions, not universal requirements.

A skill owning usage judgment maps its installed `.agents/tools/...` entry in
`metadata.automata-tools` and documents usage and missing-tool recovery. Runtime
instructions use installed entries, not package source paths. A standalone tool
may instead supply sufficient CLI documentation; do not invent a wrapper skill
solely to assign ownership.

## Verification

Before relying on a new tool, run `--help` and a representative command. For repairs,
verify the failure regression and a normal successful path. Durable or risky tools
also need failure-path checks and focused automated tests where they reduce risk.
Prefer smoke checks and real-task validation for one-off helpers; do not build a
large test suite unless the tool is becoming maintained infrastructure.
