---
name: automata-pi-agent-team
description: Use for controlling approved Pi workers through native RPC subprocesses, including persistent-kernel supervision and event-based returns. Not for delegation strategy or independent peer messaging.
---

# Pi Agent Team

Use native Pi RPC for worker control; agent reasoning owns task policy and result
acceptance. A task-owned Python kernel can retain subprocess handles, readers,
futures and results across interactions. This needs no parallel task controller.

1. **Establish readiness and ownership.** Confirm approval for workers, workspace,
   model/effort, effects and lifetime. Check the actual Pi CLI/RPC version and
   prepared kernel/client environment; availability of this skill proves neither.
   Use existing Python-kernel and background-process guidance for generic mechanics.
   Own one subprocess and its sole stdio connection; never take another controller's
   pipes or concurrently resume an active session. Record effective session/model/
   thinking from native `get_state`, not just launch flags; do not silently fall back.

2. **Use native commands.** Preserve native JSON shapes, response IDs, errors and
   prompt disposition. Read installed Pi's `docs/rpc.md`, `rpc-commands.md` and
   relevant event/API references when needed. Keep the LF-only stdout reader and
   separate stderr drain active before dispatch. Retain handles in the same kernel
   across correlated executions; bound waits, records and retained evidence.
   See [kernel/RPC mechanics](references/kernel-rpc.md) for the focused workflow.

3. **Return evidence by event.** Prompt acceptance is not execution settlement;
   `agent_settled`, not `agent_end`, ends automatic continuation. Neither proves
   task success. Store the result before notifying the coordinator through an
   approved wake path, such as the existing Pi NodalWire bridge. Verify actual
   receipt and live result lookup, not only relay acceptance. Yield rather than
   poll; a bounded coordinator watchdog is a failure fallback, not normal delivery.

4. **Recover and finish deliberately.** A timeout/cancelled wait may leave work
   running; inspect correlated evidence before another consequential command.
   Never automatically replay/restart or turn a permission refusal into approval.
   Preserve results, stop owned child/readers/notifier, shut down the kernel when
   no longer needed, and verify exits. Live objects are not durable memory.

## Existing extension compatibility

The `agent_*` extension may still be installed; this workflow does not retire it.
If using its tools, read `README.md` in the **active installed bundle** and follow
its contracts, not native commands sent through a second owner. Locate it in
`.pi/extensions/pi-agent-team/` or the configured agent directory (default
`~/.pi/agent/extensions/pi-agent-team/`); respect `PI_CODING_AGENT_DIR` and explicit
package/extension locations. Missing tools or dependencies need an authorized
setup decision, not an implicit install/reload or control takeover.
