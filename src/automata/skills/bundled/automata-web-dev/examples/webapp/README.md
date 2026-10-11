# Primitive Foundation Example

Three small design pages using FastAPI/Jinja2, Deno/esbuild and the maintained
Adaptive UI source. `/` redirects to `/design/tokens/`, with colour, spacing,
corners, lift and transparency specimens. `/design/typography/` owns the h1–h6
scale and reading specimens; `/design/components/` shows Button, Card and a thin
Form. No backend interaction or persistent state is demonstrated.

## Run a project copy

Requires uv, Deno, Node and cached dependencies. Do not build inside installed
skills. Resolve this helper against the web-dev skill directory:

```sh
python scripts/create.py --output /path/to/owned/webapp
```

Use `--adaptive-ui /path/to/automata-adaptive-ui` for a non-sibling installation.
The helper refuses an existing destination and records absolute file-URI imports
in the copied `deno.json`. Keep that selected source available. From the copy:

```sh
uv sync --locked --offline
deno install --cached-only --allow-scripts=npm:esbuild
deno task check
deno task build
deno task dev
```

Open http://127.0.0.1:8017/. Missing caches require explicit permission to fetch
packages; no global runtime installation is needed. Build before starting the
backend because its static mount requires `browser/`. The build runs trusted local
code with full Deno permissions and starts esbuild.

Use `deno task watch` for frontend rebuilds. Uvicorn reloads Python changes;
refresh the browser for updated templates/bundles. There is no browser hot reload.
Stop owned commands with Ctrl+C. Changing routes in an already running non-reload
preview requires restarting that backend, not just copying templates.

## Source layout

```text
app/main.py                   # Three page routes, home redirect and assets mount
app/templates/_base.html      # Shared ordinary page CSS and design navigation
app/templates/base.ts         # Registers Button/Card/Form and mounts page examples
app/templates/design/
  tokens/index.html           # Colour, spacing, corners, lift and transparency
  tokens/index.ts             # Registers page-owned sections
  tokens/_index/              # Section components and local helpers
  typography/index.html      # Dedicated typography page composition
  typography/index.ts        # Registers its reading specimen
  typography/_index/         # Type scale, reading and component-owned CSS
  components/index.html      # One example and short usage per primitive
  components/index.ts        # Browser-local example responses
browser/base.js               # Generated bundle, not maintained source
scripts/build.ts              # Deno-driven esbuild build/watch
```

Only explicit pages and `/browser/` are served. Template sources and source maps
are not public. FastAPI's API-documentation pages are disabled for this example.
The copy helper rewrites source aliases; esbuild mirrors them. This is a source
dependency, not a portable published browser package. Independent shipping needs
an intentional packaging choice. Existing `.js` imports of `.ts` source retain
Deno's sloppy-imports option.

## Primitive values and components

`@adaptive/tokens` exposes the current `color`, `effects`, `radius`, `spacing` and
`typography` primitives. The 45 raw colors use canonical families/shades from the
[official GNOME palette](https://developer.gnome.org/hig/reference/palette.html).
That reference intends them for icons and illustrations; choosing them for UI
primitives here is an application decision, not native compliance. Effects are
separate transparency/alpha values, not extra official palette colors.

The shared browser entry applies the typography primitives to all three pages:
a fluid document root grows from 15px to 17px between 600px and 1200px. Body is
`1rem`; h1–h6 use `2.25`, `1.875`, `1.5`, `1.25`, `1.125` and `1rem`. Labels use
`.85rem`; local `em` sizing remains available when parent-relative sizing is
wanted. All existing `rem` spacing scales with the root too. Headings use weight
600 and line height 1.25; body uses weight 400 and line height 1.5.

Component-owned CSS references primitive values and emits concrete CSS. Page CSS
owns layout. There are no semantic role layers, custom-property override APIs,
mode selectors, scoped paint factories or appearance-validation models.

- **Button:** native button inside a light-DOM wrapper. `label`, `type` and
  `disabled` are simple attributes; disabled follows presence semantics, so
  `disabled="false"` still disables. Typed creation data can set those same native
  properties without a mandatory configuration schema.
- **Card:** plain content container. Compose your own HTML inside it.
- **Form:** wraps an existing native `<form>` or moves its HTML children into one.
  Native controls/constraints own input validation. `aui-form-submit` bubbles and
  is composed, with `{ values }` derived from native FormData. It prevents
  navigation, not validation, and does not clear fields. Repeated names use the
  last entry in this small values object; file inputs retain native File values.

`Base` extends Adapter and supports registration, typed `create({ data,
children })`, and `applyData`. Custom components may use its existing
`validateData` hook for meaningful actual data; appearance is not a data schema.
No form-definition DSL, transport controller or production-hardening framework
is included.

## Design references and limits

The [GNOME HIG](https://developer.gnome.org/hig/) primarily guides native
GTK/libadwaita applications. Browser work can borrow its
[design principles](https://developer.gnome.org/hig/principles.html),
[accessibility guidance](https://developer.gnome.org/hig/guidelines/accessibility.html)
and [adaptiveness guidance](https://developer.gnome.org/hig/guidelines/adaptive.html)
without claiming native widgets or certification.

A typecheck/build does not establish visual quality, WCAG compliance or production
readiness. These pages are a small working foundation for human preview, not an
assertion campaign about colors, spacing or typography.
