---
name: automata-pi-workers
description: Use for launching, controlling, resuming or collecting results from separate Pi agent workers or subagents. Not for choosing team composition or managing ordinary non-agent subprocesses.
---

# Automata Pi Workers

Operate a separate Pi process within an approved delegation envelope; this skill
does not grant launch authority or provide a native spawn tool. Delegation owns
briefing and acceptance; process guidance owns external-process supervision.

Consult the installed Pi package's `docs/cli-integration.md`, `docs/cli.md`,
`docs/rpc.md`, `docs/rpc-commands.md` and `docs/json.md`, plus its CLI help, for
current options and wire contracts. These are Pi package docs, not project files.
Do not build a supervisor framework or copy their API reference into task guidance.

1. **Choose the interface.** Prefer print mode for a bounded final-text result,
   JSON mode for one-shot structured events, and RPC for a persistent worker that
   needs later input or state inspection. RPC supports ordinary Python subprocess
   pipes; prefer an available maintained client when it fits the host language.
   Use `automata-python-kernel` only when retaining handles and async tasks helps;
   ordinary scripts suffice otherwise. `automata-background-process` owns lifecycle.

2. **Launch with deliberate context.** Select the authorized CWD, model, effort,
   tools, resources and session policy. Account for discovered extensions and MCP,
   not just built-in tools. Noninteractive project trust can skip needed resources;
   resolve that deliberately rather than automatically approving a project.
   Context files can load even without project trust. CWD, worktrees and tool
   selection are not OS sandboxes. Supply a bounded brief, not a copied parent
   session or replacement system prompt by default; preserve applicable instructions.

3. **Verify readiness and the return path.** For RPC, inspect `get_state` before
   dispatch: verify the reported model, thinking level and session identity rather
   than trusting launch flags. Stop on unsupported settings or mismatches; do not
   silently substitute. Verify required resources and transport separately.
   Direct RPC output can return bounded work. For asynchronous NodalWire messaging,
   use `automata-nodalwire`: the coordinator's Pi receiving integration must be
   connected and able to inject follow-ups; a Python receiver or saved log alone
   does not wake it. Establish delegation's verified callback and bounded watchdog
   before dispatch. A watchdog in the same kernel cannot cover loss of that kernel.
   If the return path cannot be established, use bounded synchronous work or pause.

4. **Keep RPC observable.** Subscribe/read before sending the assignment, correlate
   command responses by ID, and drain stdout and stderr even when results travel
   over NodalWire. Parse stdout as LF-delimited JSON records, not diagnostic text
   or generic Unicode line splitting. Prompt success means accepted, queued or
   handled, not completed; a handled prompt may start no run. Handle extension UI
   dialogs within authority or cancel/escalate them; unattended dialogs can stall.

5. **Interpret completion.** For JSON/RPC runs, wait for `agent_settled`, not merely
   `agent_end`, which may precede automatic continuation. Settled means no automatic
   work remains, not task success. Inspect final messages, abort/error/truncation
   evidence and requested artifacts before acceptance. JSON-mode exit zero alone
   does not establish success. Correlate the worker's result to its assignment;
   late or unsolicited messages do not authorize new work.

6. **Resume and stop precisely.** Record the owned process and Pi-reported session
   identity; resume that worker only, not whichever session is most recent. An
   in-memory session cannot be resumed after exit. Abort does not necessarily clear
   queued work; account for pending prompts before cancellation or reassignment.
   Closing RPC stdin requests orderly shutdown; verify process termination through
   its lifecycle owner. Kernel loss does not prove worker exit. Retain results and
   owned reconnect details until delegation acceptance or an authorized handoff.
