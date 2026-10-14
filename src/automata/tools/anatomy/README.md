# automata-anatomy

One read-only, loopback-only tool for **monitoring and canonical skill reading**.
FastAPI + Jinja serve ordinary documents; Adaptive UI supplies components and a
shared semantic theme. Skill examples are non-executing text, not a simulator or
code executor. Team is a separate tool under `../team/`.

## Run

Prepare Automata's optional `anatomy` extra only with installation authority. Core
CLI help, skill installation/export and Team help do not require web dependencies.
With an already-prepared environment:

```sh
automata-anatomy serve --port 8766
# Foreground serving is also the default action:
automata-anatomy --port 8766
# Source checkout:
PYTHONPATH=src python -B -m automata.tools.anatomy.cli serve --port 8766
```

Open `http://127.0.0.1:8766/` for the monitor, or `/skills/` for the catalog. Run
from the project to monitor: project roots and activity scope follow the invocation
CWD; canonical bundled inventories come from the Automata package, not a guessed
checkout path. No service is detached automatically. Ctrl+C/SIGTERM stops it.

`automata anatomy`, `automata skill-builder` and `python -m automata.skills.cli`
remain lightweight aliases for the same tool. Their `export-agent` command keeps
whole canonical skill export without importing viewer dependencies. The default
serve port is now 8766; use `/skills/`, not a second server at port 8788.
The retired `automata.apps.dashboard.server` module is replaced by the command
above; there is no maintained `apps/` source category or duplicate server.

`automata tools install --tool anatomy --target-root /chosen/tools` copies this
tool, including its viewer assets. `/chosen/tools/anatomy/anatomy.py` launches that
copy with an already-installed Automata package and the `anatomy` extra. The
package supplies canonical skills: the tool copy does not duplicate them. The
ordinary package entry point is named `automata-anatomy`.

## Chart assets and offline preparation

Reviewed Adaptive UI, Mermaid and Prism bundles and notices ship with the tool.
Both monitor and skill components share `/lib/adaptive-ui.js` and the same theme.
The monitor additionally needs the pinned official ECharts 6.0.0 standalone ESM
asset. Prepare it from already-cached Deno/npm dependencies into owned runtime
storage; missing dependencies require separate preparation approval.

```sh
# Repository checkout; explicit output can be an owned task-evidence directory.
cd src/automata/tools/anatomy/frontend
deno run --cached-only --allow-read --allow-write=/chosen/anatomy-public \
  build.ts /chosen/anatomy-public
# Back in the project to monitor, use the already-prepared Python environment:
automata-anatomy serve --asset-root /chosen/anatomy-public
```

The default chart root is `.agents/var/tools/automata-anatomy/public/` under the
invocation project. `deno task build` prepares that root in a source checkout;
`--asset-root` supports installed packages and isolated tests. Missing chart assets
return a bounded 503; they are never fetched remotely by the server or browser.
Only `/lib/echarts.js` is public, not its source maps, package tree or notices.
No installed-copy or old dashboard-cache migration happens automatically.

## Documents and safe public boundary

- `/` and `/automata/` redirect to `/automata/index.html` (monitor).
- `/api/anatomy` retains the read-only aggregate monitoring contract.
- `/skills/` lists all 44 recursively discovered canonical skills and search.
- `/automata-workplan/` (also `index.html`) displays exact `SKILL.md` source.
- Discovered references, such as
  `/automata-agent-evaluation/references/scoring.html`, render Markdown.
- `/skills/NAME/SKILL.md` returns exact canonical raw source for discovered names.
- Old `/templates/index.html` redirects to `/skills/`; old skill/reference query
  view URLs remain supported. Retired skill names remain unavailable.

Canonical skills and supporting assets live directly in `../../skills/`.
`catalog.py` owns website routes; `templates/skills/` owns viewer templates,
components, reviewed libraries and notices. `server.py` owns one lifespan/watcher,
Host/Origin/CSP protections and a closed public asset registry.
`routes/automata.py`, `data.py` and `activity.py` retain the monitor projection.

The complete skill source (frontmatter, fences, whitespace and final newline) is
Jinja-autoescaped. Prism highlights without executing examples and retains official
line-number gutters. References use Mistune, never Jinja evaluation; authored raw
HTML is escaped. Mermaid enhances authored fences using strict sanitization and
HTML labels disabled. Relative Markdown links become discovered document links.

Only exact discovered documents, raw landing sources and explicitly registered JS
and notice assets are served. Other supporting skill files install/export but are
not public viewer routes. Never mount templates, installed-skill roots, dependency
trees or the repository as a static directory. Base templates, Python, arbitrary
Markdown, source maps and outside/symlink escapes are denied. API docs are disabled.

All routes require the exact loopback Host and same Origin when supplied. CSP has
no inline scripts, `unsafe-eval`, CDN or extra connection destinations; shared SSE
is same-origin. This remains a trusted-local development/read-only tool, not an
authenticated production deployment. Profiles, credentials and private evidence
stay outside public assets.

## Navigation, state and live authoring

The shared shell links monitor and catalog; appearance preference uses the single
`anatomy-theme` key. Monitor navigation is a full-document load, preserving timer
and request ownership. Skill-to-skill links have progressive fetch/swap enhancement
with native View Transitions and normal-navigation fallback. Modified clicks and
Back/Forward remain available. Reduced motion skips transitions.

Monitor state (tab, search/setup/selection, range/timezone/skill/chart limit,
custom dates and pause) stays in validated URL parameters. The navigation remembers
only allowlisted monitor query parameters in sessionStorage, never snapshots or
arbitrary destinations. Browser history works without storage. Returning obtains
one initial snapshot even when paused but does not re-enable periodic polling.
Unload stops timers and aborts pending fetches; skill pages mount no monitor and
make no monitoring API requests. Back-forward cache restoration establishes a fresh
owned lifecycle.

One watcher watches canonical skills and the complete Anatomy template tree.
`/__anatomy/events` (old `/__skill_builder/events` alias retained) has bounded SSE
subscribers. Markdown and shared template/component changes reload both monitor
and skill documents without build/sync. Serving writes neither source nor generated
output. Python changes require restart. If watched roots disappear or the watcher
fails, restore them and restart. SSE reload resets transient page state. The
watcher cancels at shutdown; browser EventSources close at page unload.

## Monitoring data/time contracts

Monitoring retains 5-second polling, pause/manual refresh, DST-aware charts,
keyboard tabs and last-good failure recovery. Identity shows global Pi AGENTS.md
as escaped read-only text without following its referenced files. On-disk files
prove neither live session context nor authentication/readiness. Capabilities link
tools only through explicit `metadata.automata-tools` declarations.

Activity reads only the existing recorder's SkillActivation contract scoped to the
invocation project, returning aggregates, not session IDs/histories/chats/work items.
Missing events do not prove recorder uptime or actual inactivity. The reader stays
serialized; source failures are bounded 503 responses without private exceptions.

`GET /api/anatomy?range=7d&timezone=Asia%2FBangkok&skill=automata-timer` retains
`activity.window/timeline/bucket/skillOptions`. `24h` is rolling with hourly buckets;
`7d`/`30d` include today plus previous 6/29 local days. Custom dates are inclusive
in their IANA zone, capped at now for today, limited to 366 days, and reject future
or reversed dates. UTC filtering is start-inclusive/end-exclusive. Counts,
timeline and ranking share filters; the separately labeled last-24h figure covers
all project skills. Invalid selections return readable 422 details.

## Focused checks

Use the already-prepared development environment and an owned test-output root:

```sh
PYTHONPATH=src python -B -m pytest -q tests/apps/dashboard tests/apps/skill_builder \
  tests/cli/skill_builder_test.py
node --test tests/apps/dashboard/*_test.mjs tests/apps/skill_builder/*_test.mjs
ruff check src/automata/tools/anatomy tests/apps/dashboard tests/apps/skill_builder
```

Native skill browser tests cover exact numbered source, reference diagrams and
canonical source edits reloading via SSE. Monitor browser acceptance uses synthetic
API fixtures, a prepared chart root and an owned isolated server. It checks shared
catalog navigation/return, polling/pause, restored state, charts, themes, keyboard,
validation/outage and mobile layout. These checks do not establish production
security, recorder uptime, agent behavior or installed runtime activation.
