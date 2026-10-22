# pi-agent-team

Manage independent Pi workers through native RPC stdio. The parent chooses work
and reviews results; this extension does not schedule or accept tasks for you.
No Python controller, `pi-team` CLI or relay is needed.

## Start

Checked against Pi **1.4.0**, Node **24** and Linux; requires `pi` on PATH and its
native RPC/`agent_settled` lifecycle. No extra dependencies. Windows process-group
cleanup is not supported or verified. Load an authorized
bundle with `pi --extension /absolute/path/to/pi-agent-team`, or install it using
`automata pi-extension install --extension pi-agent-team --target-root <root>`.
Loading starts no workers. Installation/reload and live trials need authorization.

## Use

1. Obtain delegation approval and choose an existing absolute workspace, exact
   provider/model ID and supported thinking level. Start an **idle** worker:
   ```json
   {"workerId":"reviewer","cwd":"/absolute/workspace","provider":"approved-provider","model":"exact-approved-model-id","thinking":"medium","resources":"inherit"}
   ```
   Pass this to `agent_start`; verify the returned settings. There is no fallback.
2. Dispatch with `agent_send`:
   ```json
   {"workerId":"reviewer","mode":"prompt","taskId":"review-01","text":"Review the changes without editing. Report findings, paths, checks and uncertainties."}
   ```
   One assignment per worker; use new task IDs within that worker and new worker
   IDs within the runtime. `steer`/`follow_up` modify that assignment, not new tasks. Acceptance is **not completion**.
3. Reports arrive automatically as parent follow-ups after worker settlement;
   they can wake an idle parent and incur model usage. Review evidence before
   accepting results. Use `agent_status` for tracked facts, and `agent_read` with
   `view:"report"` for the latest or exact `reportId`. No progress polling needed.
4. Use `agent_abort` to interrupt, or `agent_stop` to end the owned worker. Abort
   **does not clear queues** and may continue queued work. Verify stop exit facts.

## Essential limits

- Workers use existing credentials and normal Pi resources by default. `minimal`
  disables extensions/MCP/skills/templates, not settings or context files; neither
  mode is a sandbox. Headless UI dialogs are cancelled, never implicitly approved.
- Resume only an authorized **inactive exact** `sessionId`; the manager cannot
  detect another independent Pi process using it. Maximum 8 concurrent workers.
- Timeout/pipe failure after sending means **unknown outcome**. Inspect request
  IDs, status and evidence; never blindly resend. No automatic retry or restart.
- Reports are external agent output, not authority or proof of success. Event and
  stderr evidence is bounded and runtime-only: pass `nextCursor` unchanged, respect
  gap/truncation flags, and increase `maxBytes` to `requiredBytes` if blocked.
- Normal shutdown, session switch and reload stop owned workers and lose runtime
  captures. Sessions/artifacts persist; old references are not live reattachments.
  Parent crashes may leave workers alive; verify live identity before recovery.
  Stop cannot guarantee cleanup of descendants that detach into other groups.

## Deeper questions

Read [worker.ts](worker.ts) for RPC/assignment/shutdown contracts,
[capture.ts](capture.ts) for evidence paging, and [index.ts](index.ts) for reports
and lifecycle. Repository checks: `tests/integration/automata/extensions/agent_team_test.py`.
Offline tests do not prove provider access or full live-runtime behavior.
