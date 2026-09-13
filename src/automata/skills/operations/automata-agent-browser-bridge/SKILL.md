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

Identify the intended endpoints and their owner. Reuse a suitable connection after
checking its current status and identity, not merely a listening port or old record.
Use the mapped tool's `--help` for commands and its browser API documentation for
integration; reuse the shipped client and server rather than regenerating them.

```bash
uv run --offline --no-project --script .agents/tools/agent-browser-bridge/agent_browser_bridge.py --help
```

`setup` prepares runtime assets; `serve` starts the listener. Neither launches an
agent. In Pi, `agent_browser_bridge` opens the binding to the current intended
session; it does not start the server. Establish missing installation through the
appropriate setup capability, within existing authority.

Keep pairing credentials and endpoint records out of public assets and logs. Use
loopback unless broader access is authorized. Retain enough endpoint and process
identity for reconnection and owned cleanup; revalidate after session changes.

## Exchange

Carry complete bounded JSON without projecting it onto component-specific fields.
Components own payload and reply semantics; the bridge is independent of UI choice.
Use the exact message ID as `replyTo` and the component's complete reply as `payload`
with `action=send`. Keep the binding open while the interaction continues.

Use canonical message/tool-call records rather than adding duplicate transcripts.
Browser provenance does not grant authority for shell, file, or external actions.

## Verify and recover

Verify a correlated browser-to-agent-to-browser exchange. Distinguish connection,
server receipt, Pi admission, reply delivery, and component handling; a transport
receipt or terminal-only answer is not an end-to-end result.

Check busy/disconnect behavior when relevant. Do not silently replay an uncertain
send. Revalidate affected endpoints and routing when earlier evidence is no longer
current; repair only the affected setup. In-memory correlation does not promise
durable history or exactly-once business execution.

## Close

When the interaction ends, close its binding and stop only owned bridge services
that are no longer needed. Preserve pages and evidence; stopping a connection does
not authorize deleting them.

## Boundaries

This skill owns connection, delivery verification, and recovery judgment. UI
construction, component contracts, browser control, delegation, and installation
belong to their respective capabilities. Command options and protocol mechanics
belong to the tool; task-specific policy stays with the task.
