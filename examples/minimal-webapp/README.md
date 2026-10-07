# Minimal Webapp

A working integration example: uv + FastAPI + Jinja2, Deno + esbuild,
and Adapter Web Components. This is the first slice; design tokens and
GNOME-inspired visual details are provisional, not a finished design system.

## Run

Requires uv, Deno, and a checkout of this repository. From this directory:

```sh
uv sync --locked
deno install --allow-scripts=npm:esbuild
deno task build
deno task dev
```

Open http://127.0.0.1:8017/. In another terminal, run `deno task watch` for
frontend rebuilds. Uvicorn reloads Python changes. Refresh the browser for
new frontend/template content; browser hot reload is not implemented.
Stop each command with Ctrl+C. Build before starting the backend: its
static mount expects `browser/` to exist.

```sh
deno task check
```

The Deno build task runs trusted local code with full permissions and
starts esbuild. Dependencies are project-local; uv/Deno generate lockfiles.
No global dependency installation is needed.

## Layout

```text
app/
  main.py                     # Explicit page routes and built-assets mount
  templates/
    _base.html                # Internal shared layout, inherited by all pages
    base.ts                   # Shared browser entry, loaded by the base layout
    index.html
    about.html
    design/
      tokens/index.ts         # Typed scales, semantic tokens and theme overrides
      components/counter.ts   # Adapter-based example component
browser/base.js               # Generated output, ignored by Git
scripts/build.ts              # Deno-driven esbuild build/watch
```

Only explicit page routes and `/browser/` are public. Template sources are
not mounted, and underscore naming is a convention, not access control.
No source maps are emitted. The component's count is browser-local and
resets on page navigation; no database or API interaction is implied.

## Shared foundation

This repository demo imports the maintained Adaptive UI `Base`, `Button`,
`Card`, and semantic tokens through the Deno import map. `Base` extends
Adapter; npm dependencies use the pinned Adapter JSR distribution and
Edictor validation used by the catalog. esbuild aliases mirror the import
map and resolve dependencies from this example's local `node_modules`.

This avoids duplicating Adaptive UI's foundation. Copying the example out
of the repository requires updating these source aliases; it is not yet a
standalone published skill package. The existing library uses `.js` imports
for `.ts` files, so its established Deno sloppy-imports option is retained.

## Design direction

[GNOME HIG](https://developer.gnome.org/hig/) informs the compact header,
clear focus indication, readable content, and semantic palette. This is a
web adaptation, not GTK/libadwaita or full native HIG compliance. Detailed
token/component design is intentionally the next step, not part of this
integration slice.
