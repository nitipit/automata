---
name: automata-python-workspace
description: Use when an agent needs a persistent Python workspace to inspect, experiment with, or modify live objects across interactions, optionally shared with a browser interface. Not for ordinary one-shot scripts or repeatable batch execution.
metadata:
  automata-tools: .agents/tools/python-runtime/python_runtime.py
---

# Automata Python Workspace

Use a live Python namespace when keeping the same objects helps investigation:
loaded datasets, parsed code, simulations, connections or debugging fixtures.
Browser interaction is an optional example, not the capability's prerequisite.

## Choose the state model

Prefer ordinary scripts when inputs and steps are known, the filesystem already
holds the important state, or another person or process must reproduce the result.
Use a live workspace when follow-up questions benefit from the same object
instances rather than repeatedly rebuilding or serializing them. Neither choice
needs a benchmark campaign; test the uncertain benefit with a bounded experiment.

Live state is ephemeral, not durable memory. Save useful conclusions and procedures
as requested artifacts, scripts or tests. Do not automatically replay execution
history after a crash: it may repeat external effects.

## Establish an owned workspace

Use the shared entry `.agents/tools/python-runtime/python_runtime.py` with
`uv run --script`; consult its `--help` for the installed interface rather than
building a second custom REPL. Skill installation alone does not install the tool
or its dependencies.
Confirm readiness and obtain authority for missing setup or new persistent
processes; do not silently install or expose a network service.

Choose a task-owned working directory and environment. Keep installed skill and
tool assets read-only; put runtime state outside them, normally under
`.agents/var/tools/python-runtime/` or the approved task area. Record only what
is needed to reconnect and stop safely: runtime identity, endpoint, working
directory and lifecycle owner. Revalidate saved handles before reuse. Never
attach to another task's kernel merely because it is reachable.

A Python kernel is not a sandbox. It can use its process's filesystem, network,
credentials and subprocess permissions. An execution request does not authorize
unrelated reads, external messages or destructive effects. Keep arbitrary Python
execution on the intended trusted local interface, not exposed to browser pages.

## Work with live state

Execute through the workspace client, not an unrelated one-shot Python process.
Use bounded outputs and execution deadlines; disable interactive stdin. Identify
requests and the current runtime generation so stale results are not attributed
to a new session. Let the runtime enforce serialization and message correlation.

Inspect deliberately. Prefer explicit primitive projections over dumping an
entire namespace or automatically formatting arbitrary objects: properties,
representations and inspection expressions can execute code. Minimize sensitive
output and retain it only within the task's authority.

When sharing state with a UI, keep one authoritative object owner. Send explicit
commands and publish explicit snapshots/events; a rendered copy is not a second
authority. Arbitrary Python mutations do not imply automatic UI notifications.
Distinguish pending commands, confirmed results and disconnection. Reconnecting
must not silently replay actions. Coordinate disruptive tests and restarts when
a person is using the workspace.

## Failure and recovery

An exception, timeout or interrupt may leave objects partially mutated. Do not
infer rollback from an error, or retry a consequential operation before checking
its outcome. Interrupt is best effort; native code may not respond. Surface
unknown or unhealthy state instead of presenting an old snapshot as current.

A restart loses live objects and does not undo file writes, network requests or
other external effects. Use the runtime's interruption and restart contract;
verify the new generation and readiness. Confirm before discarding valuable live
state unless recovery authority already covers that loss.

Verify proportionately: demonstrate object continuity across separate calls and
inspect actual results. For a browser bridge, check both directions and distinguish
runtime checks from observed browser behavior. Report unverified limits rather
than promoting a working demo into a claim of general reliability.

## Finish and retain

Leave a workspace running only for authorized continued use, with ownership and
reconnection details. Otherwise stop the exact owned runtime and verify shutdown.
Do not assume stopping a kernel cleans up arbitrary detached child processes or
external resources; account for those effects separately.

Stopping does not authorize deleting artifacts, profiles, history or evidence.
Review accumulated session state when closing or reusing a workspace; preserve
needed results and seek scoped cleanup authority. Avoid automatic retention of
code or output that may contain secrets.

## Browser example

The bundled `examples/browser-counter/README.md` provides an optional worked
example. Copy its source to an approved task area before running it; do not build
or create live state inside the installed skill. Use it to explore shared object
state, not as a required server architecture for every Python workspace.
