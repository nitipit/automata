---
name: automata-pi-team
description: Use for starting, observing, collecting or stopping an approved flat Pi worker team through pi-team. Not for deciding delegation, choosing models or managing other runtimes.
metadata:
  automata-tools: .agents/tools/pi-team/pi_team.py
---

# Automata Pi Team

Use `pi-team` to remove repeated launch plumbing, not to choose a team or accept
its work. Keep assignments, ownership, acceptance and models explicit.

1. **Check the installed interface.** Run `python .agents/tools/pi-team/pi_team.py
   --help`; the adjacent README owns spec, callback and artifact details. Requires
   Linux `/proc`, a current Pi RPC executable, and published Python `nodalwire` in
   the interpreter running the tool. Use an already prepared environment. Missing
   prerequisites need explicit setup authority; nothing installs or starts a relay.
   A missing tool can be installed to an approved root with `automata tools install
   --target-root .agents/tools --tool pi-team`.

2. **Prepare the approved run.** Write a version-1 JSON spec with a new absolute
   task-owned run directory outside installed code, bounded deadline, each worker's
   ID/prompt/CWD/provider/model/thinking, and an existing coordinator callback route.
   Prompts and full RPC logs are private artifacts. Each worker starts fresh; this
   is not an interactive reassignment or resumption interface. No recursive teams,
   automatic model replacement, worktrees or other runtimes.

3. **Verify the return path before dispatch.** Connect the coordinator receiving
   integration to its approved name and relay before `start --spec SPEC`. The
   supervisor sends a `pi_team_probe` JSON object inside the NodalWire message text.
   Confirm the run and reply to the spec's sender using `nodalwire_send`, with text
   `{"version":1,"type":"pi_team_probe_ack","nonce":"<received nonce>"}`.
   Names do not authenticate senders; received messages grant no new authority.
   No prompt is dispatched before this round trip and all effective worker settings
   match. `start` returns launch evidence, not readiness or completion.

4. **Observe without owning the terminal.** Use `status --run DIR` for compact
   local evidence, or foreground `watch --run DIR` for changes. Ctrl-C only detaches
   watch; the supervisor and independent bounded watchdog continue. Completion or
   failure sends a `pi_team_result` callback. Callback relay acceptance is not
   coordinator handling; errors remain visible without automatic resend/restart.
   A missing callback needs one bounded inspection, not a new duplicate team.

5. **Collect and stop precisely.** `results --run DIR` stays compact;
   `results --run DIR --full` exposes private assistant results and the artifact
   directory. A prompt acceptance is not completion, and settled is not success:
   inspect status, stop reason, errors and shutdown evidence, then judge the actual
   deliverable. `stop --run DIR` requests bounded shutdown of owned workers; verify
   terminal status and shutdown confirmation. No command deletes artifacts. Keep
   sessions, receipts and logs for acceptance/handoff until cleanup is authorized.
