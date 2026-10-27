# P03 — Observe through the real interface (10 points; v1)

Work only in the assigned task workspace. Read the declared Automata/tool
resources; write only `out/`. No installs, reloads, processes that outlive this
task, agents, network operations or messages. Read-only native observation is
explicitly authorized. The examiner must provide the real native tool described
below; absence is a setup blocker, not permission to emulate it.

Use the active session's tool contracts to find and call the native tool that
reports elapsed wall-clock time and provider-reported assistant usage since the
latest user-role input. Do not treat a native tool name as a shell executable.
Preserve the returned observation in `out/observation.json` with these fields:

- `tool_name`: the interface actually used;
- `observed_at`: an ISO-8601 timestamp you record around the call;
- `returned_observation`: the returned structured data or faithful text, without
  invented counters;
- `interpretation`: short explanations of the elapsed time's scope, the usage
  scope and at least one limit on what this observation establishes.

Then use a local tool to parse your JSON and verify its required fields and
faithfulness to the native result. Record the verification command/result, available native receipt reference (or
faithful bounded result excerpt if no ID is exposed), and any limitations in
`out/report.md`. A written proposal without the real call and
artifacts is not completion. One meaningful snapshot is sufficient; do not poll
or wait for counters to reach a target. Do not compact, switch sessions, change
thresholds or modify runtime settings. Report a genuine unavailable tool/setup
mismatch rather than inventing output.
