---
name: automata-team-use
description: Use when publishing or inspecting goal-scoped current agent reports with the Automata Team CLI/board, or establishing its manager/member hierarchy. Not for generic team management, delegation, worker control or runtime telemetry setup.
---

# Automata Team Use

Publish **one own current-work report**, not a mirrored todo list. Learn the
validated contract from `automata team --help` and command-specific help. The app
must already be available with its optional `team` dependencies; missing setup is
not permission to install. It uses trusted-local Unix ShelfDB, not a public server.

## Establish scope

Use the agreed goal ID, own agent ID and the same explicit `--state-root` as the
running service. Default: `.agents/var/apps/agent-team/` from repository CWD.
The authorized root manager bootstraps a new graph with `init`; it never resets
existing goals. Managers publish team structure; agents publish their own reports.
`--actor` declares identity, **not authentication**; untrusted direct ShelfDB
clients can bypass permissions. Do not expose the listener or private state.

A manager represents its team. Team `manager_id`, `parent_id` and `agent_ids`
establish Manager → Alice → Bob. Ancestor membership does not make Bob a second
root-level direct report: ordinary members report to the deepest team's manager.
A manager's highest managed team establishes its parent. Avoid ambiguous sibling
membership; the board diagnoses competing managers rather than guessing.
No worker starts/stops, assignments or delegation authority come from this app.

In an Automata checkout, this sample has the hierarchy above and no tasks/usage:

```sh
automata team init --goal example-reports --actor manager \
  --file examples/team/reports.json --state-root .agents/var/apps/agent-team
```

For another goal, change the goal record's `id`, every record's `goal_id` and
`--goal` together. Goal-local agent/team IDs **may repeat across goals**; keep
IDs and the manager/member hierarchy unambiguous within each goal.
A missing/null agent `report` shows unavailable; legacy tasks never supply it.

## Publish meaningful changes

After the manager establishes membership, Alice starts one report through the
ordinary agent update command. All initial report fields except the server-owned
status timestamp are included; unavailable observations are null:

```sh
automata team update --goal example-reports --actor alice --kind agent --id alice \
  --file - --state-root .agents/var/apps/agent-team <<'JSON'
{"report":{"summary":"Implementing current-report publishing","status":"working","blocker":"","elapsed_seconds":null,"estimate":{"min_seconds":null,"max_seconds":null,"target_finish":null},"tokens":{"input":null,"output":null,"cache_read":null,"cache_write":null,"observed_at":null,"source":"unavailable"}}}
JSON
```

Update when the work changes, a material blocker appears, the estimate changes or
completion is verified, not on every activity. Patches recursively merge; omitted
fields survive. Supply a real dependency/decision for blocked status:

```sh
automata team update --goal example-reports --actor alice --kind agent --id alice \
  --file - --state-root .agents/var/apps/agent-team <<'JSON'
{"report":{"status":"blocked","blocker":"Awaiting approved interface decision"}}
JSON
```

Resume with `status: working` and clear the blocker. Completion reports the actual
verified result, not acceptance or a new assignment:

```sh
automata team update --goal example-reports --actor alice --kind agent --id alice \
  --file - --state-root .agents/var/apps/agent-team <<'JSON'
{"report":{"summary":"Verified current-report publishing","status":"done","blocker":""}}
JSON
```

`put --kind agent` creates/replaces a complete own agent record; prefer `update`
for changing its report without dropping profile/context. Do not patch identity,
`updated_at` or `report.status_changed_at`. Metric/same-status updates preserve the
status time; actual transitions change it. Errors are stderr/nonzero with no
partial writes; report the error rather than resetting the goal.

Estimates are declared expectations (`min_seconds`, `max_seconds`, optional offset
ISO `target_finish`), not observed duration. Publish `elapsed_seconds` only when
actually known. Token counts need an actual observation timestamp and `source:
measured`; samples use `sample`. Context is separately published on the agent,
never inferred from billed tokens. Do not attribute whole-session usage to current
work without measurement supporting that scope. Missing measurements stay null,
not zero. This app has no automatic runtime telemetry.

## Inspect without controlling

```sh
automata team json --goal example-reports --kind agent --id alice \
  --state-root .agents/var/apps/agent-team
automata team board --goal example-reports --state-root .agents/var/apps/agent-team
```

The board stays in that goal: top=current agent, table=direct reports once each,
bottom=selected agent, all using the same report. → opens the selected agent only
when it has direct reports. A leaf stays selected on its parent's board, with its
own report in the bottom panel; repeated → leaves route/history/selection unchanged.
← returns to the real parent and restores selection; Enter toggles the selected
panel, q closes only the viewer. A root with no children still shows its own report.

This bundled skill is discoverable as `automata-team-use` through the normal
Automata skill catalog. Load it for this app's publishing contract; packaging does
not globally expose it, activate it or prove an agent follows it.
