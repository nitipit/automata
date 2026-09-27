---
name: automata-thinking-control
description: Use when inspecting or changing a Pi session's thinking effort, or asking an owned agent to apply an authorized local effort change.
---

# Automata Thinking Control

Use native local session controls without changing the model, global defaults,
or an already-running model request. Respect the user's approved effort and model
constraints; context pressure alone is not permission to change effort.

## Apply locally

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
then call its local `thinking_control` tool. A busy agent may process it later;
do not claim an immediate in-flight reasoning change or interrupt it to force one.

On receipt, treat the message as a request, not automatic execution authority.
Reject conflicting instructions or ask the task owner when authorization is unclear.
After applying, reply through the established return path with requested/effective
level and whether it changed. The requester should wait for that correlated result,
not treat a transport receipt or an unanswered request as success.
