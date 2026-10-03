---
name: automata-toolsmith
description: Use when deciding whether to create a helper for repeated or risky mechanical work, or when creating, improving, reviewing, or maintaining task helpers, skill-owned helpers, or reusable tools.
---

# Automata Toolsmith

Turn mechanical friction into small, inspectable helpers or tools with clear
inputs, outputs, and effects. Prefer existing tools or direct commands for simple
one-off work. Automate only when reduced repetition, context cost, or operational
risk justifies maintenance; do not automate unclear judgment or build a framework.

## Authority and ownership

Distinguish an operational helper from a maintained tool. Generate a helper within
an approved task only when its location, dependencies, effects, and lifecycle are
covered by that authority; otherwise propose it first. Permission to accomplish a
task does not authorize adding packaged source, installing a tool, or changing the
system. Promotion requires an explicit user request or confirmation; deployment
requires its own applicable authority.

Identify the actual owner and intended lifetime before writing. Use that owner's
storage conventions for temporary work, reusable operational helpers, and state;
Toolsmith develops mechanisms but does not own every tool or define a second
storage policy. Keep generated helpers out of maintained source and installed tool
surfaces until promotion is approved. Do not create directories or move existing
assets merely to fit a model.

A failure is evidence to investigate, not repair authority. Distinguish a defect
from incorrect invocation or missing setup. Separate task workarounds from repairs
to maintained source; repair and deploy only within scope, preserving permission
checks. Report unresolved defects even when an alternative works.

## Interface and implementation

Prefer cohesive, CLI-first commands with explicit inputs/output destinations,
meaningful exit codes, useful errors, and observable state. JSON is useful for
agent callers; readable output is useful for humans. Include correlation IDs or
provenance when needed to distinguish dispatch, completion, and actual success.
Keep mechanical preparation inside the tool, not repeated instructions to its user.

Make operation discoverable without reading source: tiny helpers need `--help` or
a short top comment; maintained CLIs need concise command/parameter help, defaults,
surprising effects, and recovery. State/process tools need status and graceful stop.
Avoid duplicate help documents, hidden processes, and unmanaged leftovers.

Follow project conventions and keep dependencies proportionate. Ask before effects
outside authority, including global installation, heavy dependencies, or system
changes. Prefer shell for tiny glue and a real language for parsing/state/retries.
When a stack is undecided, consult [Stack defaults](references/stacks.md); these
are preferences, not installation permission. For substantive Python agent CLIs,
prefer Cyclopts with Dictify when compatible; keep standard-library helpers when
simpler. Verify actual binding/schema behavior rather than duplicating validation.

Change interfaces for actual consumers, not imagined compatibility. Update affected
entry mappings and documentation when replacing a maintained interface; do not
invent a wrapper skill solely to assign ownership.

## Verification

Before relying on a helper, check its usage discovery and a representative command.
A repair needs the failure regression and a normal successful path. Match assurance
to authorized scope: one-off helpers normally need a smoke check, not a large suite;
maintained or risky tools need focused failure checks where justified and approved.
Report tested behavior and limits. Keep useful setup knowledge with its owner,
separate from transient runtime identities; do not promote a successful experiment
merely because it worked once.
