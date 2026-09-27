# Automata dashboard (development)

Read-only, loopback-only dashboard for global identity, capability setup and
project-scoped recorded skill loads. FastAPI + Adaptive UI + Arrow + ECharts.
No conversations, knowledge store, work tracking, or new telemetry.

## Build and run

Run from the repository root. Python, Deno, Node and the pinned dependencies must
already be cached; these commands do not fetch missing dependencies implicitly.

```sh
python .agents/skills/automata-adaptive-ui/scripts/build.py \
  --runtime-root .agents/var/apps/dashboard/public
(cd src/automata/apps/dashboard/frontend && deno task build)

PYTHONPATH="$PWD/src" uv run --offline --no-project \
  --with fastapi==0.141.1 --with uvicorn==0.53.0 \
  --with shelfdb==3.0.2 --with dictify==5.0.2 --with pyyaml==6.0.3 \
  python -B -m automata.apps.dashboard.server --port 8766
```

Open http://127.0.0.1:8766/. This is a source-checkout development application,
not an installed CLI or production deployment. No core dependency changes.
Missing dependencies require separate, authorized preparation; the frontend pins
ECharts 6.0.0 in `frontend/deno.json` and `deno.lock`.

Python source, UI source in `web/`, and Deno build inputs in `frontend/` are
maintained here. Generated browser files and dependency notices are built into
`.agents/var/apps/dashboard/public/`. The server exposes explicit routes only,
never a repository directory or the surrounding runtime tree. Keep credentials,
profiles, reports and private runtime state outside the served assets.

Rebuild after frontend edits, then reload the page. Restart the server after
Python edits. Adaptive UI is built through its existing builder without changing
skill source or another session's assets. Task-specific evidence and live process
handles remain in the task workspace, not in maintained app source.

## Data boundaries

- Identity displays global Pi AGENTS.md as escaped read-only text, without
  following referenced files. An edit does not prove a running session reloaded it.
- Capabilities group skill copies by name, including shared and Pi-specific
  bundled skills. Only explicit `metadata.automata-tools` entries link tools.
  Installed files do not prove authentication, connection or runtime exposure.
- Activity reads the existing recorder with its actual SkillActivation contract,
  scoped to this repository, and returns aggregates. Review reads count;
  incomplete reads and recorder gaps limit interpretation. No session IDs or
  histories are served. Zero recorded events does not establish recorder uptime.

## Time contract

`GET /api/anatomy?range=7d&timezone=Asia%2FBangkok&skill=automata-timer`
returns identity, capabilities and `activity`. Statistics fields such as `window`,
`timeline`, `bucket` and `skillOptions` are nested inside `activity`.

- `24h` is rolling; `7d` and `30d` include today and the previous 6/29 local days.
- Custom `start` and `end` dates are inclusive in the selected IANA timezone,
  capped at now for today, limited to 366 days, and reject future/reversed dates.
- UTC filtering is start-inclusive/end-exclusive. Hour buckets serve `24h`;
  other ranges use local calendar-day buckets, including DST transitions.
- Total, timeline and ranking share the same range/skill filter. The separately
  labeled last-24h figure covers all project skills, independently of selection.
- Available-record bounds describe observed records, not recorder uptime.
- Invalid selections return 422 with a readable `detail`; the UI keeps last-good
  data rather than silently substituting another timezone or range.

Themes use semantic CSS variables in `web/themes.css`; `web/theme.js` manages
light/dark/system preference and emits `anatomy-theme-change`. Theme changes keep
current tabs and filters. Polling runs every 5 seconds, with pause/manual refresh.
