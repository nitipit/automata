# Canonical skills

This directory owns canonical skills, nested skills and all supporting assets.
Markdown discovery and agent export belong to `../tools/anatomy/content.py`.
Every skill is discovered recursively through `SKILL.md`; there is no `bundled/`
layer or duplicate catalog.
The current catalog has 44 skills, including nested children.

The web family lives in `automata-web-design/`, with Adaptive UI and Web App under
its `skills/` directory. Other families preserve their existing nested layout.
Agent instructions, reference Markdown, templates, scripts and libraries remain
inside their owning skill package.

## Human reading

The viewer belongs to [automata-anatomy](../tools/anatomy/README.md), not this
source category. One local server provides monitoring, the `/skills/` catalog,
exact skill source and linked reference views, with shared navigation and theme.
Viewer Python, Jinja templates, components and reviewed browser libraries all
live under `../tools/anatomy/`.

With the optional `anatomy` dependencies already prepared:

```sh
automata-anatomy serve --port 8766
automata anatomy serve --port 8766
python -m automata.tools.anatomy.cli serve --port 8766
```

Open `http://127.0.0.1:8766/skills/`. Serving reads canonical Markdown directly and
never writes, installs or synchronizes skill sources. See the Anatomy README for
public route boundaries, rendering, live reload and optional chart assets.

## Agent installation and export

`automata skills install` installs outer parent packages. Selecting a parent
includes its nested children and supporting assets once. A nested child is not a
separate installation unit; select its outer parent rather than creating duplicate
flat exposure. Existing obsolete flat installations are not removed automatically.
Use explicit retirement/replacement and backup authority when migrating them.

```sh
automata skills install --target-root /chosen/agent/skills --skill automata-web-design
# Exact whole-skill export, including nested child exports when explicitly requested:
automata-anatomy export-agent automata-agent-design --output /chosen/export
```

`export-agent` copies the complete canonical skill, without importing FastAPI or a
renderer. Supporting assets install/export with their skill but do not become
public website files. Installing the renamed `automata-workplan` does not remove
an existing `automata-plan` installation. Source disappearance never authorizes
installed-copy deletion.

Focused checks cover recursive discovery, nested installation units, canonical
copy/export, wheel resources and the unified viewer's literal source/reference
rendering and live reload. These mechanical checks do not establish agent judgment
or runtime activation.
