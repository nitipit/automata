---
name: automata-agent-browser-bridge
description: Use when connecting a browser interface to an agent session, establishing a reusable browser-agent bridge, or recovering an existing connection.
metadata:
  automata-tools: .agents/tools/agent-browser-bridge/agent_browser_bridge.py
---

# Automata Agent Browser Bridge

Connect the intended browser and agent, verify delivery, and recover or close the
connection without losing ownership or confusing transport state with outcomes.

## Connect or reuse

Consult relevant saved setup knowledge before reconstructing commands. Reuse a
connection only after checking its status, intended endpoints and ownership—not
merely a listening port or old record.
Use the mapped tool's `--help` for commands and its browser API documentation for
integration; reuse the shipped client and server rather than regenerating them.

```bash
uv run --offline --no-project --script .agents/tools/agent-browser-bridge/agent_browser_bridge.py --help
```

`setup` prepares runtime assets; `serve` starts the listener. Neither launches an
agent. In Pi, `agent_browser_bridge` opens the binding to the current intended
session; it does not start the server. Establish missing installation through the
appropriate setup capability, within existing authority.

Use loopback unless broader access is authorized. Keep pairing credentials and
endpoint records out of public assets and logs; retain live identity only for
reconnection and owned cleanup, revalidating after session changes.

After setup discovery succeeds, save verified startup, connection, status-check,
and owned cleanup commands with prerequisites, working directories and variable inputs
in approved owner-scoped data, separate from live endpoint records. Report the recipe's
location; exclude live session identifiers and do not duplicate tool documentation. Do not retain pairing secrets as setup knowledge
or treat saved setup as permission.

## Exchange

Carry complete bounded JSON without projecting it onto component-specific fields.
Components own payload and reply semantics; the bridge is independent of UI choice.
Use the exact message ID as `replyTo` and the component's complete reply as `payload`
with `action=send`. Keep the binding open while the interaction continues.

Use canonical message/tool-call records rather than adding duplicate transcripts.
Browser provenance does not grant authority for shell, file, or external actions.

For context without a new request, use the client's context delivery options:
`nextTurn` queues data for the next prompt; a named slot replaces its pending value.
Use `inspect_context` or `clear_context` to manage pending data, not history.
Consult tool documentation for `steer`, `followUp`, and trigger behavior. Distinguish
buffered, queued, and attached receipts; none proves the model acted on the data.

## Verify and recover

Verify a correlated browser-to-agent-to-browser exchange. Distinguish connection,
server receipt, Pi admission, reply delivery, and component handling; a transport
receipt or terminal-only answer is not an end-to-end result.

Check busy/disconnect behavior when relevant. Do not silently replay an uncertain
send. Revalidate affected endpoints and routing when earlier evidence is no longer
current; repair only the affected setup and update the recipe after verification.
In-memory correlation does not promise durable history or exactly-once business execution.

## Close

When the interaction ends, close its binding and stop only owned bridge services
that are no longer needed. Preserve pages and evidence; stopping a connection does
not authorize deleting them.

## Boundaries

This skill owns connection, delivery verification, and recovery judgment. UI
construction, component contracts, browser control, delegation, and installation
belong to their respective capabilities. Command options and protocol mechanics
belong to the tool; task-specific policy stays with the task.
