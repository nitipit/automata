---
name: automata-thinking-control
description: Use when inspecting or changing a session's thinking effort, or asking an owned agent to apply an authorized local effort change.
---

# Automata Thinking Control

Use native local session controls without changing the model, global defaults,
or an already-running model request. Respect the user's approved effort and model
constraints; context pressure alone is not permission to change effort.

## Runtime dispatch

Use the host's exposed controls, not the model/provider name, to select a path.

- **Pi with `thinking_control`:** follow the local workflow below.
- **Native Codex CLI:** this Pi tool is unavailable. The human can use native
  model/effort controls for the current session; preserve the approved model when
  choosing effort. Do not edit global config or restart into a different model
  to simulate a local change. If no agent-callable local control is exposed,
  report that limit and request the human action only when needed. A configured
  value or accepted API string is not proof of supported or effective effort.
  Report the native confirmation and its scope, or leave effectiveness unknown.
- **Other hosts:** require an available documented local control; do not invent
  tool calls or silently substitute a supported level for an unsupported request.

No path changes reasoning already in flight. The rest of the local tool workflow
is Pi-specific; the authority and correlated-reply requirements apply to all hosts.

## Apply locally (Pi)

Use `thinking_control action: "inspect"` to read the current model, supported
levels and effective native effort. For an authorized change, use `action: "set"`
with an exact supported `level`. Unsupported levels fail rather than falling back.

Read `requested`, `effective` and `changed` in the result. The change updates
session state now and affects the next model request, including continuation after
tools. It cannot change reasoning already streaming. Do not abort or restart work
to pretend otherwise. Native effort is not a measurement of provider reasoning
budget. Report a failure rather than claiming the requested level was applied.

## Ask an owned agent

Use existing `automata-tmux-communication` and `automata-delegation` guidance for
an owned or assigned agent, within the user's communication and task authority.
This capability does not create a remote control channel or grant new authority.
Do not address unrelated agents or infer permission from a reachable pane.

Ask the intended target to apply the authorized level and reply with its effective
setting. Forwarding or tmux submission is not application: the target must first
process the message, check conversational authority against its own task constraints,
then apply its available local control (`thinking_control` in Pi). If the target
has no such control, it must report that limitation. A busy agent may process it later;
do not claim an immediate in-flight reasoning change or interrupt it to force one.

On receipt, treat the message as a request, not automatic execution authority.
Reject conflicting instructions or ask the task owner when authorization is unclear.
After applying, reply through the established return path with requested/effective
level and whether it changed. The requester should wait for that correlated result,
not treat a transport receipt or an unanswered request as success.
