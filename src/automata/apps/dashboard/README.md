# Anatomy (development)

Read-only, loopback-only **FastAPI + Jinja monitoring app**, with Adaptive UI
components and local ECharts. Its Skill catalog link opens the separately
launched Skill Builder site; Anatomy neither renders nor serves installed skills.
Normal links load independent documents. No SPA, router connection, simulator,
or code executor.

## Pages

- `/automata/index.html`: Identity, Capabilities and Statistics local tabs.
- Skill catalog: `http://127.0.0.1:8788/` links canonical skill source and references.
- Retired Message Router guide routes return 404.

Guide usage belongs in the canonical Markdown, not this README. Examples are
non-executing text. Anatomy never reads router endpoint records or starts the
skill-site server.

## Offline build and run

From the repository root, with Python/Deno and pinned dependencies already cached:

```sh
# Reuse the existing built Adaptive UI library. If absent/stale, its documented
# builder requires cached prerequisites; obtain approval before any download.
python .agents/skills/automata-adaptive-ui/scripts/build.py \
  --runtime-root .agents/var/apps/dashboard/public
(cd src/automata/apps/dashboard/frontend && deno task build)
PYTHONPATH="$PWD/src" uv run --offline --no-project \
  --with fastapi==0.141.1 --with uvicorn==0.53.0 --with jinja2==3.1.6 \
  --with shelfdb==3.0.2 --with dictify==5.0.2 --with pyyaml==6.0.3 \
  python -B -m automata.apps.dashboard.server --port 8766
```

Open `http://127.0.0.1:8766/`. This is a source-checkout development app, not a
production deployment or installed CLI. Jinja is an app-local runtime recipe,
not a new core dependency. Isolated cached resolution does not install globally.
Missing dependencies require separate approval/preparation; no implicit downloads.
The Deno task uses `--cached-only`, pinned ECharts 6.0.0 and Mermaid 11.12.2.

For the optional guide, run a separate owned process using cached dependencies:

```sh
PYTHONPATH=src uv run --offline --no-project \
  --with fastapi==0.141.1 --with jinja2==3.1.6 --with mistune==3.3.4 \
  --with watchfiles==1.3.0 --with uvicorn==0.54.0 --with cyclopts==4.25.3 \
  python -m automata.skills.cli serve --port 8788
```

This command serves and watches canonical Markdown directly; no website build,
per-skill HTML wrapper or agent export is needed. See [Skill Builder](../../skills/README.md)
for catalog mode, restart boundaries and Markdown-only agent export. Anatomy's
link targets default port 8788; open a custom skill-site port directly.

## Maintained structure and public boundary

- `server.py`: FastAPI, loopback Host/Origin/CSP protections and closed asset list.
- `routes/automata.py`: monitor document and compatible `/api/anatomy` endpoint.
- `templates/base.html`: private monitor inheritance.
- `templates/automata/index.html` and matching `index.css.js`: monitor page;
  `components/monitor.js`, `monitor-state.js`, `activity-chart.js` own its lifecycle.
- `../../skills/bundled/`: canonical skills and supporting assets shared by agents
  and the human website.
- `../../skills/templates/`: shared website templates, components, reviewed
  libraries and notices. Native Engrave output lives in owned temporary storage,
  never in the installed agent skill or dashboard templates.
- `templates/shared/theme.js` and `shared/components/anatomy-nav.js`: shared
  semantic tokens/theme preference, catalog registration and normal document links.

Source co-location matches URLs: `/automata/components/monitor.js` serves its
maintained module, using relative imports. `.css.js` files are JavaScript modules,
not standalone stylesheets. Component styles live inside the component modules.
Only explicitly registered JS files are public. Templates render through Jinja;
base templates, arbitrary files, source maps and dependency source are denied.
Never mount the whole `templates/` tree or repository as a static directory.

The central dependency cache is `.agents/var/apps/dashboard/public/lib`.
Anatomy exposes only Adaptive UI and ECharts through explicit `/lib/*.js` routes.
The separate skill site explicitly serves reviewed Adaptive UI/Mermaid/Prism.js
assets under `/templates/` and selected raw `SKILL.md` files. Its loopback
FastAPI/Jinja preview is distinct from Anatomy's protections; see the Skill Builder
README. Agent export copies all canonical skill assets; Anatomy exposes no guide
libraries or installed-skill directories.
Old generated SPA files remain unreachable. Reload after monitor JS/template edits;
restart after Python route changes. Keep profiles, credentials and evidence outside
public assets. Anatomy CSP has no inline scripts, `unsafe-eval`, CDN or additional
connection destinations; the separate site's native localhost SSE supports refresh.

## Monitoring and navigation contract

`/` and `/automata/` redirect to `/automata/index.html`. The Skill catalog link
opens the independently launched site; old Router lesson redirects are retired.
Old hash-only SPA bookmarks are intentionally retired: the root redirect reaches
the default monitor, and any retained fragment has no routing
meaning. There is no hash router or arbitrary redirect input.

Monitoring retains 5-second polling, pause/manual refresh, timezone/custom dates,
DST-aware charts, keyboard tabs, semantic themes and last-good failure recovery.
The selected tab, capability search/setup/selection, range, timezone, skill,
chart limit, custom dates and pause state are serialized into its URL. Restoration
validates choices, IANA timezone, bounded strings and date syntax. Invalid URL
values use documented UI defaults; live invalid form selections still receive
readable API errors and never silently replace last-good data. Dates outside the
API's permitted window remain API validation errors.

The host navigation remembers only these query parameters in sessionStorage;
it never stores data snapshots or arbitrary destinations. The separate skill site
intentionally has no Anatomy return link or shared theme preference. Return via
browser Back or a bookmarked monitor URL; both restore state even if storage is
disabled. A return loads one initial snapshot even when paused, but **does not
re-enable periodic polling**.
On page unload timers stop and in-flight fetches abort. Guide documents mount no
monitor and make no API requests. Back-forward cache restoration reloads the saved
URL to establish a fresh, owned lifecycle. Theme preference alone uses localStorage.

## Data and time boundaries (unchanged)

- Identity displays global Pi AGENTS.md as escaped read-only text, without following
  referenced files. On-disk instructions do not establish live session context.
- Capabilities group skill copies by name; only explicit `metadata.automata-tools`
  entries link tools. Installed files prove neither authentication nor readiness.
- Activity reads the existing recorder's SkillActivation contract, scoped to this
  repository, returning aggregates. No session IDs, histories, chats or work items
  are served. Missing events do not establish recorder uptime or actual inactivity.

`GET /api/anatomy?range=7d&timezone=Asia%2FBangkok&skill=automata-timer`
returns identity, capabilities and `activity`; window/timeline/bucket/skillOptions
are nested inside `activity`. The reader remains serialized and errors are bounded.

- `24h` is rolling; `7d`/`30d` include today and the previous 6/29 local days.
- Custom dates are inclusive in the selected IANA zone, capped at now for today,
  limited to 366 days, and reject future/reversed dates.
- UTC filtering is start-inclusive/end-exclusive. Hour buckets serve `24h`;
  other ranges use local days, including DST transitions.
- Total/timeline/ranking share filters. The separately labeled last-24h figure
  covers all project skills. Available-record bounds are not recorder uptime.
- Invalid selections return 422 with readable detail; source failures return a
  bounded 503 without exposing private exception contents.

## Focused verification

```sh
PYTHONPATH=src uv run --offline --no-project \
  --with fastapi==0.141.1 --with uvicorn==0.53.0 --with jinja2==3.1.6 \
  --with shelfdb==3.0.2 --with dictify==5.0.2 --with pyyaml==6.0.3 \
  --with engrave==3.2.6 --with pytest --with httpx pytest -q tests/apps/dashboard
node --test tests/apps/dashboard/*_test.mjs
uv run --offline --no-project --with ruff ruff check \
  src/automata/apps/dashboard tests/apps/dashboard

# Real isolated Chrome; use an explicitly owned, already-built preview.
# Every API read is intercepted by synthetic fixtures: no live identity/recorder read.
ANATOMY_EVIDENCE=/absolute/task/evidence/fresh-run \
  uv run --offline --no-project --with playwright \
  python tests/apps/dashboard/browser_acceptance.py
```

`ANATOMY_URL` defaults to `http://127.0.0.1:8766/`. Browser checks cover actual
external guide navigation, URL restoration, pause/poll lifecycle, charts,
validation/outage recovery, desktop/mobile, keyboard and themes. Both API reads and
the guide destination are intercepted by synthetic fixtures. Native skill-site
rendering, diagrams and canonical Markdown edit/rebuild/browser refresh are tested
separately in `tests/apps/skill_builder/`. Temporary browsers always close.
Screenshots supplement assertions. No live router service is contacted.
