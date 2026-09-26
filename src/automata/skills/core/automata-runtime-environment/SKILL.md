---
name: automata-runtime-environment
description: Use when a task depends on agent-runtime or execution-environment facts that are not already known in context, or when evidence indicates those facts have changed.
---

# Automata Runtime Environment

Discover only unknown environment facts needed for the task, such as active
settings, available interfaces, configuration sources, or execution constraints.
Choose an appropriate inspection method for the actual runtime; stop when there
is enough evidence to proceed. This is not a routine startup check or machine
inventory.

Treat the environment as normally stable within a session. Keep findings in
conversation context and reuse them without repeated verification unless evidence
indicates a relevant change. Findings apply to the environment inspected, not
automatically to another worker, host, or execution context.

Distinguish observed facts from defaults, preferences, and assumptions. If a needed
fact cannot be established within authorized access, explain the specific gap
rather than guessing or expanding the investigation.

Inspection does not authorize configuration changes or access to secrets. Do not
create or update persistent environment documentation unless the user explicitly
requests it; existing notes do not authorize further writes or cleanup.
