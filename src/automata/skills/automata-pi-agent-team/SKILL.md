---
name: automata-pi-agent-team
description: Use for starting, resuming, assigning, inspecting, aborting or stopping managed Pi workers with the pi-agent-team extension. Not for independent peer messaging or general delegation strategy.
---

# Pi Agent Team

Before first use in a session, read `README.md` in the **active installed
`pi-agent-team` extension bundle** for prerequisites, workflow and limitations.
Look in the project's `.pi/extensions/pi-agent-team/` or the configured Pi agent
directory's `extensions/pi-agent-team/` (default
`~/.pi/agent/extensions/pi-agent-team/`). Respect `PI_CODING_AGENT_DIR` and any
explicit extension/package location; use the bundle actually loaded, not a source
checkout or unrelated copy. If it cannot be located or its `agent_*` tools are
missing, report the gap; do not install or reload without authorization.

Use only approved workers, workspaces and model/thinking settings. Choose
`agent_start` for a new session (no `sessionId`); choose `agent_resume` only for an
authorized inactive existing session with its exact full ID. After launch failure,
inspect diagnostics and exit facts before correcting the call; do not repeat the
same failed call or guess session names/IDs. The extension owns worker mechanics,
not assignment judgment or result acceptance. Follow the README and exposed tool
contracts; inspect code/TSDoc only for deeper questions.
