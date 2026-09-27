# Thinking control (Pi)

Local inspection/application using native `getThinkingLevel` and `setThinkingLevel`.
No model switching, global persistence, request aborting or remote control API.
Tested against Pi 0.87.1.

Install the `thinking-control` extension and `automata-thinking-control` skill
through the normal Automata installers. Call `thinking_control`:

```json
{"action":"inspect"}
{"action":"set","level":"high"}
```

Results include the current session/model, supported levels, requested/effective
native level, previous level, changed and busy state. Unsupported effort is
rejected before application. Supported levels come from Pi AI model metadata,
including null exclusions and explicit xhigh/max mappings. No active model fails
closed. Native effort is not a measurement of a provider's actual reasoning budget.

The setter updates session state immediately; **the next model request** observes
it, including continuation within the same run. A request already using its
snapshot is unaffected. The tool never aborts it. Native Pi records changed levels
in the session transcript and does not persist a global default through this API.

To ask another owned/assigned agent to change effort, use existing authorized tmux
communication and delegation. The target must process the message, check authority
against its task constraints, call this local tool, and reply with the effective
setting. Forwarding the request does not prove application. This extension adds
no transport, grant files, permissions, event-bus control lane or remote execution.

## Validation boundaries

`thinking_control_test.py` opts into the installed native Pi SDK through
`AGENT_BROWSER_BRIDGE_NATIVE_PI_PACKAGE`. A local streaming provider verifies
next-request timing, session transcript, unsupported effort and unchanged global
defaults without paid calls. Tests also exercise the local tool while a request is
streaming; this isolates the native timing boundary, not conversational handling
of a tmux message. Live provider budget mapping and agent judgment are not tested.
