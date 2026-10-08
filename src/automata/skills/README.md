# Skill Builder

All 38 bundled skills live in `bundled/automata-*/`. Discovery follows each
`SKILL.md` and linked Markdown under `references/` or `templates/`.
There are no per-skill HTML wrappers, generated entry files or build output.
Shared Jinja templates render each request directly from canonical Markdown.

## Run

With the dependencies already cached (no network needed):

```sh
PYTHONPATH=src uv run --offline --no-project \
  --with fastapi==0.141.1 --with jinja2==3.1.6 --with mistune==3.3.4 \
  --with watchfiles==1.3.0 --with uvicorn==0.54.0 --with cyclopts==4.25.3 \
  python -m automata.skills.cli serve --port 8788
```

`serve` always includes all discovered skills. Open `http://127.0.0.1:8788/`.
The catalog lists all 38 skills with immediate links and a client-side search over
skill names, titles and descriptions. Search leaves the complete static catalog usable
without JavaScript.

Public views:

- `/`: catalog; `/templates/index.html` redirects to `/` for compatibility.
- `/templates/skill.html?name=automata-agent-design`: source view.
- `/templates/reference.html?name=automata-agent-evaluation&reference=references/scoring.md`:
  rendered reference view.
- Retired Router and Playspace routes are no longer served.
- `/automata-workplan/` and `/automata-workplan/index.html`: workplan source view.
  The retired `automata-plan` name and `/plan/` alias are no longer served.

## Rendering and boundaries

The complete `SKILL.md`, including frontmatter, fences and final newline, is placed
in the page with Jinja autoescaping. Prism highlights the literal Markdown, using
its official line-number plugin; Mermaid fences in that source remain code.
Reference Markdown is rendered by Mistune in Python, **never evaluated as Jinja**.
Authored raw HTML is escaped. Local components enhance reference code and diagrams;
examples are not executed. Relative Markdown links become public view links.

Only exact discovered skill/linked-Markdown selections and explicitly allowed
shared assets are served. Other supporting assets install with their skills but
are not public viewer routes. Assets remain together in `templates/components`, `templates/lib`,
`templates/licenses`, and the two CSSJS files. Shared views are rendered, never
returned as HTML source. Private base/includes, Python, arbitrary Markdown, outside
paths and symlink escapes are denied. The optional raw `skills/<name>/SKILL.md`
route returns canonical source for discovered skills. FastAPI API-documentation routes
are disabled. This loopback-only development server is not production hosting:
there is no authentication, strict Host/Origin policy or production deployment setup.

## Browser loading and navigation

Early theme CSS avoids an unstyled first paint. Undefined page components remain
hidden until registration, with a four-second reveal fallback if modules fail.
Internal page links use a small fetch-and-swap layer with native 180ms View
Transitions when supported; reduced-motion preferences skip the animation.
Back/Forward and normal modified clicks remain available. Redirected navigation
uses the final canonical URL in browser history. Failed enhancement falls back to
full navigation; no Swup dependency or per-skill client templates are needed.

## Live authoring and lifecycle

One `watchfiles` watcher watches only `bundled/` and `templates/`. Its bounded SSE
subscribers receive change events at `/__skill_builder/events`; the browser reloads
and requests fresh source. Markdown edits, template edits and new discovered skills
need no build or source synchronization. Python or port changes require a server
restart. SSE reload resets transient page state. If watched roots are removed or the
watcher fails, restore them and restart the preview.

Serving writes neither the package/source tree nor generated output, so it does not
require writable installed sources. Authoring naturally requires write access to
the canonical files. `Ctrl+C` / SIGTERM stops the app and its watcher. No task scratch
path is needed to run or retain the preview. Anatomy only links this separate site.

All reviewed local bundles and exact notices remain in `templates/lib` and
`templates/licenses`. Prism 1.30.0 provenance is in
[prism-PROVENANCE.txt](templates/licenses/prism-PROVENANCE.txt). Official line numbers
are CSS counters in an aria-hidden, unselectable gutter. Code does not wrap; tabs
and final newlines are retained. Unknown languages remain literal with line numbers.
If Prism would change whitespace such as NBSP, the component falls back to literal
text rather than altering source. Existing Adaptive UI themes, layout and inline-code
styles are retained.

## Agent installation and focused verification

`export-agent NAME --output DIR` copies the complete canonical skill (including
references, scripts, libraries and templates) without importing FastAPI or a
renderer. Use installed names such as `automata-agent-design`. Serving never installs or syncs
live skills; agents read canonical files, not human-rendered output. Installing the
renamed `automata-workplan` does not remove an existing `automata-plan` installation;
remove the obsolete installed name only under separate scoped migration authority.

`tests/apps/skill_builder/test_build.py` covers direct public views, denial boundaries,
reference Jinja/HTML literal handling, and disposable installation of selected
skills. `test_browser.py` covers catalog entries with exact numbered
source, a synthetic reference diagram, and one source edit reloading via SSE.
Catalog search/navigation and CLI tests cover the direct serving contract;
running focused checks does not claim the broader suite passed.
