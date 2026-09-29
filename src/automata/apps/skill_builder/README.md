# Skill Builder

Build complete ready-to-install skills from one canonical authoring location.
The first builder is Message Router. This app owns authoring and build output,
not installation, router operations, or preview hosting. There is no plugin system.

## CLI

From the repository root, use uv's shared cache without changing the project or
installing globally. Prepare Engrave 3.2.6 with `uv run --no-project --with
engrave==3.2.6 engrave --help` only when dependency downloads are authorized.
Subsequent builds are offline:

```sh
PYTHONPATH=src uv run --offline --no-project --with engrave==3.2.6 \
  python -m automata.apps.skill_builder.cli --help
PYTHONPATH=src uv run --offline --no-project --with engrave==3.2.6 \
  python -m automata.apps.skill_builder.cli message-router --help
PYTHONPATH=src uv run --offline --no-project --with engrave==3.2.6 \
  python -m automata.apps.skill_builder.cli message-router
```

The Cyclopts entry point parses options and invokes the concrete builder. The
optional `--output /path/to/skill` names the **complete skill directory**, not its
`webref/` subdirectory. `--library-root /path/to/cached/lib` overrides the existing
central bundle directory. No command downloads dependencies, installs skills,
launches browsers, or starts the router.

## Source and output

`message_router/` is the sole authoring source:

- `SKILL.md`: canonical agent instructions and activation frontmatter.
- `content/*.md`: explanatory reference content and literal fenced code examples.
  A small amount of trusted structural HTML embeds sections and diagram components.
- `site/`: Engrave/Jinja layout and page `.css.js` modules defining Adaptive UI
  page components. The shared `ReferencePage` owns scoped layout/theme CSS and
  theme listeners; other components own their styles. Adapter registers `this.css`
  through constructable `adoptedStyleSheets`, never head-injected style tags.
  Only a minimal document reset uses a separate adopted stylesheet.
- `licenses/`: exact library licenses and provenance, copied beside the bundles.
- `build.py`: concrete complete-skill build; no generic framework or installer filtering.

Generated output is `src/automata/runtimes/pi/skills/automata-message-router/`:

```text
automata-message-router/
├── SKILL.md
└── webref/
    ├── index.html
    ├── configure.html … failures.html
    ├── components/
    ├── index.css.js … failures.css.js
    └── lib/  # local Adaptive UI, Mermaid, licenses and provenance
```

Do not edit generated files. Installation copies only this finished directory;
there are no authoring templates or build-time dependencies inside the skill.
The package ships the separate builder source, but using an installed skill
requires neither Engrave nor Jinja nor a router.

## Markdown rendering

Engrave's public `get_template` API provides layout and Markdown rendering.
The build passes Markdown as data through the `markdown` filter, **not** the
`markdown(path)` helper. The latter evaluates Jinja inside the Markdown first;
that would unexpectedly interpret examples containing `{{ ... }}` or `{% ... %}`.
Our path preserves them literally. Fenced code is escaped and rendered inside an
Adaptive UI code component with a keyboard-focusable scroll area.

The source `SKILL.md` is copied unchanged. Only its leading YAML frontmatter is
removed from the HTML view in Overview's expandable agent-instructions section.
Relative `webref/` links are rebased for that HTML view, not changed in the skill.
Authored Markdown is trusted repository content, not a renderer for user input.

Mermaid source lives in fenced `mermaid` blocks in `content/*.md`, beside the
explanation. Wrap each block in `<protocol-diagram aria-label="...">` with blank
lines around the fence. The build escapes the source into a hidden text block;
the component only renders it with Mermaid strict mode. JavaScript contains no
diagram-content registry. The descriptive label remains the accessible caption,
and captured source survives theme changes and component reconnection.

## Libraries and repeatability

The default input is `.agents/var/apps/dashboard/public/lib`. Builds verify the
reviewed Adaptive UI and Mermaid hashes, then render/copy local inputs. They do
not reconstruct central bundles or resolve dependency graphs. Repeated builds
with the same inputs are byte-identical. Unexpected output files fail before
writes; review them or choose a fresh output directory. No unknown files are
automatically deleted.

Adaptive UI's canonical builder is its skill's `scripts/build.py` and `lib/build.ts`.
Mermaid 11.12.2 is the official npm bundle prepared by dashboard's frontend build.
`message_router/licenses/PROVENANCE.txt` records hashes and exact license sources.
Bundle updates require deliberate hash/license review. No ECharts is shipped here.
Git whitespace checks exclude only these upstream bundles/license texts so their
reviewed bytes are preserved; authored code and generated HTML are checked normally.

## Preview and verify

```sh
python -m http.server 8788 --bind 127.0.0.1 \
  --directory src/automata/runtimes/pi/skills/automata-message-router/webref
```

Open `http://127.0.0.1:8788/`. Serve only the public-safe webref directory, never
private credentials or the repository. A normal static server is sufficient,
including below a URL prefix; `file://` is not a requirement. Anatomy optionally
serves the same bytes via a closed allowlist; it owns no second reference.

Use the cached dashboard test recipe (including `--with engrave==3.2.6`) to run
`tests/apps/skill_builder`, `tests/apps/dashboard`, `tests/cli/skill_builder_test.py`,
and the package/skill integration tests. Run the reference's Node contracts with
`node --test tests/apps/skill_builder/*_test.mjs`.

The standalone browser command is:

```sh
PYTHONPATH=src WEBREF_EVIDENCE=/absolute/new/evidence-directory \
  uv run --offline --no-project --with playwright \
  python tests/apps/skill_builder/browser_acceptance.py
```

It copy-installs into a disposable root and checks relative routes, diagrams,
themes, mobile and keyboard behavior.
The separate host test uses synthetic monitor data; neither contacts a router.
