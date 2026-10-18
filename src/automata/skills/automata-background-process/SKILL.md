---
name: automata-background-process
description: Use for launching, inspecting, collecting results from, cancelling and cleaning up external processes that continue between interactions. Not for foreground commands or purely in-kernel async work.
---

# Automata Background Process

Use ordinary Python subprocess and asyncio facilities; a persistent Python kernel
can retain process handles and background tasks across calls. Prefer the simplest
suitable existing execution method, not a new supervisor framework.

1. **Establish ownership.** Confirm the command, CWD, allowed effects and lifetime.
   Record enough identity to distinguish the owned process from a reused PID, along
   with output locations and who may stop it. Keep task state outside installed
   assets. Starting a process does not authorize installs or configuration changes.
   When using a terminal host, reuse only authorized targets; do not attach clients,
   change focus/layout or add panes to a human workspace without permission. Inspect
   only relevant owned output, without navigating to unrelated targets.

2. **Launch without blocking.** Retain handles and collection tasks, then return
   control while work continues. Keep blocking operations off the kernel event loop.
   Drain stdout/stderr asynchronously or redirect to task-owned files; bound retained
   output. A backgrounded shell command alone does not establish supervision.

3. **Inspect meaningful evidence.** Check readiness, progress or results at useful
   checkpoints, not through busy-polling. A live PID is not readiness, and a zero
   exit code is not task acceptance. When completion must wake the agent, establish
   a verified callback and failure fallback; stored output alone does not notify it.
   Delegation authority, reporting and acceptance remain with their own guidance.

4. **Recover and stop precisely.** After lost connections or uncertain launches,
   inspect before retrying to avoid duplicate effects. Kernel restart can lose
   handles without stopping children. Cancelling a collection task does not stop
   its subprocess. Stop only owned processes and descendants within authority;
   allow graceful exit, escalate when authorized, and verify termination. Preserve
   results and reconnect details for handoff; stopping grants no artifact deletion
   authority.
