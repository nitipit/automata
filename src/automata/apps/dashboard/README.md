# Anatomy (development)

Read-only, loopback-only **FastAPI + Jinja multi-page app**, with Adaptive UI
components and local ECharts/Mermaid bundles. Normal links load independent
server-rendered documents. No SPA, router connection, simulator, or code executor.

## Pages

- `/automata/index.html`: Identity, Capabilities and Statistics local tabs.
- `/message-router/configure.html`: directed permissions and private setup CLI.
- `/message-router/connect.html`: authentic browser/Node client setup; generic
  agent-kind clients are explicitly distinct from the native Pi adapter.
- `/message-router/discover.html`: caller-scoped `client.status()` and its limits.
- `/message-router/send.html`: separate independent initiation, request/reply and
  one-way lessons, each with a focused diagram, code and expected result.
- `/message-router/failures.html`: forbidden/offline, cancel and disconnect limits.

One illustrative topology is used throughout: desk/viewer pages and
worker/reviewer agents; grants desk → viewer, desk → worker, worker ↔ reviewer.
The router service is explicit in transport diagrams and is not a participant.
Permission diagrams are labeled as grants, not physical links. All guide examples
are non-executing text; credentials are placeholders, provisioned out of band in
an independently authorized setup. Anatomy never reads router endpoint records.

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

## Maintained structure and public boundary

- `server.py`: FastAPI, loopback Host/Origin/CSP protections and closed asset list.
- `routes/automata.py`: monitor document and compatible `/api/anatomy` endpoint.
- `routes/message_router_guide.py`: guide rendering only, not transport.
- `templates/base.html`, `templates/message-router/base.html`: private inheritance.
- `templates/automata/index.html` and matching `index.css.js`: monitor page;
  `components/monitor.js`, `monitor-state.js`, `activity-chart.js` own its lifecycle.
- `templates/message-router/*.html` and matching `*.css.js`: guide pages;
  `components/protocol-diagram.js` and `code-example.js` extend Adaptive UI Base.
- `templates/shared/theme.js` and `shared/components/anatomy-nav.js`: shared
  semantic tokens/theme preference, catalog registration and normal document links.

Source co-location matches URLs: `/automata/components/monitor.js` serves its
maintained module, using relative imports. `.css.js` files are JavaScript modules,
not standalone stylesheets. Component styles live inside the component modules.
Only explicitly registered JS files are public. Templates render through Jinja;
base templates, arbitrary files, source maps and dependency source are denied.
Never mount the whole `templates/` tree or repository as a static directory.

Only generated third-party bundles/notices live in
`.agents/var/apps/dashboard/public/lib`, exposed at the three explicit `/lib/*.js`
routes. Old generated SPA files may remain in an existing build directory but
are unreachable; the build no longer copies them. The retired maintained `web/`
SPA is replaced by templates. Reload after JS/template edits; restart after Python
route changes; rebuild only when dependency bundles change. Keep profiles,
credentials and evidence outside public assets.

Mermaid receives only the closed authored diagram registry, in strict mode with
HTML labels disabled. No user/URL/API content enters its SVG sink. Themes use
semantic Adaptive UI tokens; diagrams follow the theme. Flowcharts become vertical
on narrow pages; sequence diagrams retain readable width with a keyboard-focusable
horizontal scroll area. Code uses escaped HTML text, never execution or evaluation.
CSP has no inline scripts, `unsafe-eval`, CDN or additional connection destinations.

## Monitoring and navigation contract

`/` and `/automata/` redirect to `/automata/index.html`; `/message-router/` redirects
to Configure. Old hash-only SPA bookmarks are intentionally retired: the root
redirect reaches the default monitor, and any retained fragment has no routing
meaning. There is no hash router or arbitrary redirect input.

Monitoring retains 5-second polling, pause/manual refresh, timezone/custom dates,
DST-aware charts, keyboard tabs, semantic themes and last-good failure recovery.
The selected tab, capability search/setup/selection, range, timezone, skill,
chart limit, custom dates and pause state are serialized into its URL. Restoration
validates choices, IANA timezone, bounded strings and date syntax. Invalid URL
values use documented UI defaults; live invalid form selections still receive
readable API errors and never silently replace last-good data. Dates outside the
API's permitted window remain API validation errors.

A same-tab return link remembers only these query parameters in sessionStorage;
it never stores data snapshots or arbitrary destinations. If storage is disabled,
back/forward and bookmarked monitor URLs still restore state. A return loads one
initial snapshot even when paused, but **does not re-enable periodic polling**.
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
  --with pytest --with httpx pytest -q tests/apps/dashboard
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
navigation, rendered guides/assets/diagrams, URL restoration, pause/poll lifecycle,
charts, validation/outage recovery, desktop/mobile, keyboard and themes. Temporary
browsers always close. Screenshots supplement assertions and should be reviewed
for teaching clarity, not just SVG counts. No live router/Workspace service is
contacted; protocol examples are checked against shipped implementation, not
claimed as live end-to-end delivery tests.
