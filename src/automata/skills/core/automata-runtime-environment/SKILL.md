---
name: automata-runtime-environment
description: Use when a task depends on unfamiliar or uncertain agent-runtime or execution-environment facts, such as active settings, available interfaces, configuration sources, or execution constraints.
---

# Automata Runtime Environment

Discover just enough about the environment the agent is working in to make the
next task decision reliably. Support unfamiliar harnesses through evidence, not
assumed conventions. Reuse and extend verified knowledge as work reveals gaps;
do not inventory the machine or require setup before every task.

## Orient to the task

Identify the uncertainty that matters: for example, the active model and thinking
level, how a harness exposes a capability, which configuration takes effect, or
whether the current shell is inside a constrained environment. Inspect only the
facts needed to resolve it. Familiar tasks with sufficient current evidence need
no additional discovery.

Use the current tool surface, relevant project instructions, runtime metadata,
and targeted documentation or configuration reads to identify the environment.
Do not infer the harness from model identity or assume that a shell shares the
host, filesystem, permissions, or environment of another process. Current-agent
evidence does not establish a delegated worker's or remote target's environment;
obtain evidence from the intended target within authorized access.

## Reuse knowledge and inspect gaps

Consult relevant saved recipes before repeating discovery. Match their scope,
runtime/interface version, and prerequisites to this task; check only assumptions
whose change could affect the next action. A saved method can guide inspection,
but saved values are not live status and saved knowledge grants no permission.

Prefer supported read-only interfaces and the smallest useful observation. When
the method is unknown or fails, consult the applicable installed documentation,
focused help, or authoritative runtime sources before trying alternatives. Do not
guess environment variable names or scan conversation histories as a routine
fallback. Missing evidence is unknown, not proof that a capability is absent.

Distinguish:

- Current observations: what the target reports at the time checked.
- Configuration/defaults: what a source specifies, subject to precedence and
  runtime overrides.
- User preferences: desired choices, not necessarily effective settings or
  authorization to apply them.

If sources disagree, inspect only the relevant precedence or override path.
Separate observed facts from inference and explain remaining uncertainty when it
affects the task. Runtime-reported settings do not guarantee provider-side
execution. Recheck after a relevant change rather than treating a snapshot as
permanent truth.

Stop when the next task decision has sufficient evidence. If the needed source is
unavailable or outside authority, report the specific gap and a safe next option;
do not expand into unrelated environment exploration or change settings to make
inspection succeed.

### Pi starting point

For active provider, model, and thinking level in a Pi session, run through that
session's shell tool:

```bash
printenv PI_PROVIDER PI_MODEL PI_REASONING_LEVEL
```

Output follows that order. Pi injects these values when the shell tool runs;
`PI_REASONING_LEVEL` is the thinking level. Missing variables can produce fewer
lines and a nonzero exit code. If output is incomplete, inspect each named variable
separately to avoid assigning values to the wrong field; report missing fields as
unknown. This is a known starting method, not a convention for other harnesses.
Use the applicable runtime documentation when its interface differs.

## Retain useful discoveries

Keep reusable knowledge outside the skill package. Unless an existing convention
applies, use `.agents/var/skills/automata-runtime-environment/` for repository-scoped
recipes. Use `~/.agents/var/skills/automata-runtime-environment/` only for an
explicitly global scope. Make recipes findable by runtime or inspection purpose;
no mandatory index, schema, or record for every check is needed.

After useful discovery succeeds, update the relevant recipe within storage
authority: record the supported method or verified command, applicability,
prerequisites, evidence and limitations, and what would invalidate it. Retain
knowledge that avoids future discovery, not an ever-growing transcript. Consult
that knowledge on later use and expand it only as tasks require new facts.

A changed runtime/interface version, execution boundary, configuration source, or
failed check may invalidate part of a recipe. Repair only the affected knowledge
and distinguish newly verified findings from anything still uncertain. Do not
silently promote one host's observation into a universal runtime rule.

Do not copy credentials, full environment dumps, authoritative configuration, or
live handles into recipes. Keep transient observations with the work unless
continuity requires retained state; label their scope and freshness. Inspection
knowledge does not establish user preferences. At natural maintenance points,
review accumulation or conflicting recipes; merge or retire owned knowledge only
within cleanup authority, not by automatic age-based deletion.

## Boundaries and composition

This skill owns discovery of agent-runtime and execution-environment facts, not
all environment-dependent work. Project build/test recipes, browser connections,
and other specialized procedures remain with their capability owners; reuse
those rather than duplicate them here. Installation belongs to setup; model
selection and delegation retain their existing owners; context pressure and token
usage remain with context-status. Compose capabilities as needed, not as a fixed
invocation chain.

Inspection does not authorize configuration changes, dependency installation,
worker or service launches, credential reads, permission bypasses, or broader
filesystem/process inspection. Inspect named metadata and relevant non-secret
configuration fields, not entire environments or private account files. Supported
interfaces, saved commands, and discoverable resources are not permission to use
them. Retaining a recipe is separate from modifying maintained skill source or
installing it into another agent environment.
