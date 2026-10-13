---
name: automata-python-workspace
description: Use for a persistent Python namespace across interactions, optionally shared with a browser. Not for one-shot scripts or repeatable batch execution.
metadata:
  automata-tools: .agents/tools/python-runtime/python_runtime.py
---

# Automata Python Workspace

Keep live objects when continuity helps investigation; use scripts when steps are
known or reproducibility matters. Live state is ephemeral, not durable memory.
Save useful conclusions as requested artifacts, scripts or tests.

1. **Establish ownership.** Use `.agents/tools/python-runtime/python_runtime.py`
   through `uv run --script`; consult its help rather than building another REPL.
   Installation of this skill does not provide tools/dependencies. Confirm missing
   setup or persistent-process authority; do not silently install or expose services.
   Use a task-owned directory/environment, keeping runtime state outside installed
   assets, normally `.agents/var/tools/python-runtime/` or an approved task area.
   Record identity, endpoint, CWD and lifecycle owner; revalidate handles and never
   attach to another task's reachable kernel. A kernel is not a sandbox; restrict
   execution to the trusted local interface, not browser pages, and task authority.

2. **Work through the live client.** An unrelated Python process has different state.
   Bound output and deadlines; disable interactive stdin. Identify requests and runtime
   generation; let the tool enforce serialization/correlation. Prefer explicit primitive
   projections over namespace dumps or arbitrary formatting: properties, repr and
   inspection can execute code. Minimize sensitive output and retention.

3. **Share state explicitly.** Keep one authoritative object owner; send commands and
   publish snapshots/events. Rendered copies are not mutation authority, and arbitrary
   mutations need not notify a UI. Distinguish pending, confirmed and disconnected
   state; never replay actions on reconnect. Coordinate disruptive tests/restarts
   with people using the workspace.

4. **Recover without assuming rollback.** Errors/timeouts/interrupts may leave partial
   mutation; inspect outcomes before retrying consequential operations. Interrupts
   are best effort, especially in native code. Surface unknown/unhealthy state rather
   than stale snapshots. Restart loses objects but undoes no external effects; confirm
   valuable-state loss unless recovery authority covers it, then verify generation
   and readiness. Do not automatically replay history. Verify object continuity across
   calls; browser bridges need both directions and actual UI evidence, not just a demo.

5. **Close or hand off.** Leave running only for authorized use with ownership and
   reconnect details; otherwise stop the exact owned runtime and verify shutdown.
   Detached children and external effects need separate accounting. Stopping grants
   no artifact/history deletion authority; preserve needed results and seek scoped
   cleanup. Do not automatically retain secret-bearing code/output.

`examples/browser-counter/README.md` is an optional worked example, not required
architecture. Copy it into an approved task area before running; installed assets
remain read-only.
