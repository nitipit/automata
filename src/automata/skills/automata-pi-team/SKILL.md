---
name: automata-pi-team
description: Use for creating persistent Pi workers, forwarding RPC commands, reading raw events or explicitly stopping workers through pi-team. Not for deciding delegation, choosing models or autonomous team management.
metadata:
  automata-tools: .agents/tools/pi-team/pi_team.py
---

# Automata Pi Team

Use the thin CLI for process and RPC I/O, not to assign work or accept results.
The agent chooses every command, interprets output and explicitly stops workers.

1. **Check the interface when needed.** Run `python
   .agents/tools/pi-team/pi_team.py --help`; the adjacent README owns the version-2
   spec, capture and ambiguity contract. Consult the installed Pi package's RPC docs
   for native commands. Requires Linux `/proc`, Python and a current `pi` executable
   with RPC support, not the separate `pi-rpc` client or NodalWire. Reuse a prepared
   environment; missing prerequisites require setup authority, not an implicit install. A missing
   tool can be copied to an approved root with `automata tools install --target-root
   .agents/tools --tool pi-team`.

2. **Create idle workers within approval.** Supply a new task-owned run directory,
   CWD, provider/model/thinking, explicit resource/session choices and explicit
   segmented storage limits. `create --spec FILE` sends no prompt. Check open/process
   and effective-setting facts. `status --worker DIR` only reports process/storage
   facts; use RPC `get_state` to verify the effective model, thinking level and
   session identity before dispatch. Stop on mismatches rather than silently
   substituting settings. No recursive delegation, automatic model substitution,
   callback requirement or owner-loss watchdog.

3. **Forward original Pi commands.** Use `rpc --worker DIR --command FILE` for
   prompt/steer/follow_up/abort and inspection/session commands on the same worker.
   Responses are original Pi JSON; `success:false` is not a transport failure.
   Prompt acceptance is not completion. Use unique IDs; only bounded pending and
   unresolved IDs are remembered. A timeout/disconnect after dispatch is unknown
   outcome: never automatically resend. Recover late replies through raw events.
   Extension UI responses require the dialog ID and `--send-only`; local pipe
   drainage is not Pi acknowledgement.

4. **Read and judge evidence deliberately.** `events --worker DIR --cursor N
   --limit N --max-bytes N` exposes private raw stdout including responses, plus
   tagged stderr. Advance the returned exclusive cursor. Check expiration gaps,
   earliest cursor, read-budget blockage, capture errors and loss counts. Oversize
   or storage failure does not imply complete evidence; capture facts also appear
   on RPC stderr after loss. The tool continues drainage, not automatic shutdown.
   For turn completion, wait for `agent_settled`, not just `agent_end`, then inspect
   final messages, errors, abort/truncation evidence and requested artifacts.
   Settlement does not classify the task or close the worker.

5. **Resume, stop and retain precisely.** Record the Pi-reported session identity;
   resume that exact session, never whichever is most recent. An in-memory session
   cannot be resumed after exit. Before cancellation or reassignment, inspect pending
   work: abort does not necessarily clear queued instructions. The agent decides
   which to retain or cancel; the tool does not choose or clear them automatically.
   After deciding whether more commands are needed, explicitly `stop --worker DIR`;
   verify owned shutdown facts. Stopping does not imply task acceptance, and no
   command deletes artifacts. Capture
   retention bounds do not include Pi session history or worker-created files.
   Preserve sessions/evidence until authorized cleanup; do not prune user history
   or restart an unavailable controller to conceal an uncertain command outcome.
