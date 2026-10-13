# Automata Team

Runtime-neutral agents publish **one current-work report per agent** under a shared
goal. A manager represents its team. The read-only board follows the reporting
hierarchy Manager → Alice → Bob, opening agents only when they have direct reports.
Leaf Bob stays selectable on Alice's board with his report in the bottom panel.
Top=current agent, table=direct-report agents once each, bottom=selected agent.
It is not a todo mirror, worker controller or runtime telemetry adapter.

## Start, publish, inspect, stop

The optional `team` extra supplies Dictify, ShelfDB and Textual. Base Automata CLI
and Team help load without them. In a checkout with cached dependencies:

```sh
uv sync --offline --extra team
uv run --offline automata team --help
# Terminal A: trusted-local service, until Ctrl-C or SIGTERM.
uv run --offline automata team serve --state-root .agents/var/apps/agent-team
```

In terminal B from the same repository, use the optional Team-use skill asset
below. For an installed skill, resolve `assets/reports.json` relative to its
`SKILL.md` instead of using this source-checkout path.

```sh
# One NEW graph; never resets another goal. Explicitly labelled example, no tasks.
uv run --offline automata team init --goal example-reports --actor manager \
  --file src/automata/skills/bundled/automata-team-use/assets/reports.json \
  --state-root .agents/var/apps/agent-team
uv run --offline automata team update --goal example-reports --actor alice \
  --kind agent --id alice --file - --state-root .agents/var/apps/agent-team <<'JSON'
{"report":{"summary":"Implementing current-report publishing","status":"working","blocker":"","elapsed_seconds":null,"estimate":{"min_seconds":null,"max_seconds":null,"target_finish":null},"tokens":{"input":null,"output":null,"cache_read":null,"cache_write":null,"observed_at":null,"source":"unavailable"}}}
JSON
uv run --offline automata team board --goal example-reports \
  --state-root .agents/var/apps/agent-team
uv run --offline automata team json --goal example-reports --kind agent --id alice \
  --state-root .agents/var/apps/agent-team
```

`q` closes the viewer only; stop the service separately with Ctrl-C or SIGTERM.
It closes its listener/database and removes its socket, preserving records for
restart. An existing socket is never replaced. There is no record deletion API.

Every command accepts `--state-root`; default `.agents/var/apps/agent-team/` is
resolved from your repository CWD. Use the same root for all commands. Deep
worktrees may exceed the OS Unix socket path limit; use a shorter private root.
Mutable `db/` and `db.sock` live there, never in source. New directories/socket use
umask077; existing root ownership/permissions remain the operator's responsibility.

Errors are stderr/nonzero. `put`/`update` emit the resulting record, `json` emits
one record or a scoped snapshot, `init` is silent. `--file -` accepts stdin. Invalid
JSON, duplicate keys, nonfinite numbers, unknown fields and invalid graphs produce
no partial writes. `json --goal G` still includes optional legacy task records.

## One own current-work report

An agent record retains `id`, `goal_id`, `name`, `model`, `thinking`, `context`,
`updated_at`, and now an **optional nullable `report`**:

- `summary`: nonempty description of what this agent is doing now or verified.
- `status`: `pending`, `working`, `done`, `blocked`.
- `blocker`: string; blocked status requires a meaningful decision/dependency.
- `status_changed_at`: offset ISO timestamp or unavailable historical null;
  server-owned on normal publication, not a patch field.
- `elapsed_seconds`: actually observed duration or null.
- `estimate`: `min_seconds`, `max_seconds`, `target_finish`, each nullable;
  duration bounds are nonnegative and ordered, finish is offset ISO time.
- `tokens`: `input`, `output`, `cache_read`, `cache_write`, `observed_at`, `source`.
  Counts are nonnegative integers/null; known counts need an observation timestamp
  and `source: measured|sample`. `unavailable` requires unknown counts.

First publication through `update --kind agent` includes the complete report
except its server timestamp. Later patches recursively merge, preserving omitted
fields. Metrics, context-only and same-status updates preserve report status time;
genuine transitions change it. `updated_at` records each accepted agent update.
`init` preserves historical timestamps in the supplied graph.

```sh
# Material blocker; preserve summary, time, estimates and usage.
printf '%s\n' '{"report":{"status":"blocked","blocker":"Awaiting approved interface decision"}}' | \
  uv run --offline automata team update --goal example-reports --actor alice \
    --kind agent --id alice --file - --state-root .agents/var/apps/agent-team
# Verified completion; clear the blocker rather than leaving stale explanation.
printf '%s\n' '{"report":{"summary":"Verified current-report publishing","status":"done","blocker":""}}' | \
  uv run --offline automata team update --goal example-reports --actor alice \
    --kind agent --id alice --file - --state-root .agents/var/apps/agent-team
```

`put --kind agent` creates/replaces a **complete own agent record**. Prefer `update`
for report changes without dropping profile/context. Omission during update never
clears the old report; explicit `report: null`, or omission during full replacement,
means unavailable. Missing reports in legacy records remain valid and unavailable:
no destructive reset, migration, sorted-task fallback or fake progress. Legacy
`put/update --kind task` remains supported with its original ownership, placement
and timestamp rules, but tasks are neither read nor displayed by the board.

## Manager-owned hierarchy and permissions

`init` takes `goals`, `teams`, `agents`, `tasks` arrays for one complete goal graph.
Tasks may be empty. The goal's `id` equals `goal_id`; local record IDs can repeat
across different goals in the same service without collision. There is exactly one
root team whose manager is the goal manager. All referenced managers/members/tasks
must exist in the goal; team parents must not cycle, tasks link to their team/member.

Team manager/member/parent relationships define the agent view:

- A manager represents its team, not a separate extra team row. Its highest
  managed team's parent manager determines placement; the root never reports
  to a child. Repeated teams under the same manager deduplicate agents.
- An ordinary member reports to the deepest containing team's manager. Ancestor
  membership is eligibility, not another direct-report row. In the example Bob
  is eligible in root and Alice's child team but appears only under Alice.
- Competing different managers at the same placement depth are ambiguous. The
  board refuses/diagnoses this rather than selecting one arbitrarily; authorized
  structural publication can clarify memberships. Stored legacy graphs are not
  silently rewritten. Agents without membership are not fabricated as children.

The root goal manager controls goal/team structure, not others' reports/tasks;
its goal manager identity cannot be reassigned. A nested manager edits its own
team without changing its manager/parent, introduces members only from its parent
membership, and cannot add foreign task links. It may create an empty eligible
child beneath a team it manages. Agents publish only their own records/tasks;
task creation atomically links it only in a team the owner belongs to. Initial
`init` is the root manager's bootstrap exception for creating initial profiles.

`--actor` is a declaration, **not OS authentication**. Direct trusted ShelfDB
clients bypass CLI permissions; dill is unsafe for untrusted peers. Unix only,
no TCP. Do not expose state or listener to untrusted processes.

## Measurements and display

Top, table and bottom share one canonical report projection; there are no task
rows, task counts, inferred current work or subtree usage rollups. Leaf reports
remain selectable in their parent's bottom panel; a root with no children still
shows its own top report and an empty table. Goal appears once; paths contain
manager/agent names separately. Headerless Agent/Summary/Status/Time/Usage grids
wrap values beneath values. All seven table fields fit at83columns; narrower
viewports hide columns without changing stored facts. Timestamps use Bangkok time.

Unknown is not zero. Displayed report tokens sum input + output + cache-write,
not cache-read. Attribute counts to this current work only when measurement
supports that scope. Agent context is separately observed raw
`used_tokens/capacity_tokens/observed_at/source`; percentage is derived only when
both counts exist, never from billed usage. Estimates are expectations, not elapsed
facts or completion claims. No live runtime fields are invented. Sample usage is
marked SAMPLE DATA and `[sample]`; the example has unavailable measurements.

↑/↓ selects direct agents; → opens the selected agent only if it has direct reports.
Repeated → on a leaf is a no-op: route, history and selection stay unchanged.
← returns to the real parent and restores selection; Enter toggles the selected
panel. q stops polling and awaits any in-flight read before closing only the viewer.
Refresh/navigation are read-only; the goal never changes in that board.

## Usage skill and checks

The bundled `automata-team-use` skill teaches this app's hierarchy/publishing
contract with exercised CLI/JSON examples. It is discoverable through the existing
Automata skill catalog; packaging is not a global installation or activation.
Its scope is app use, not generic management/delegation/runtime setup.

Saved unit, actual console/ShelfDB integration and headless UI tests are under
`tests/apps/team/{unit,integration,ui}`:

```sh
uv run --offline pytest -q tests/apps/team
uv run --offline ruff check src/automata/apps/team tests/apps/team
```

Integration fixtures own private Unix servers/writers and stop them in `finally`.
These checks do not establish authenticated identity, real runtime measurements,
fresh-session skill behavior or production/network reliability.
