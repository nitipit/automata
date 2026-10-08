# Webapp Example

A working integration example: uv + FastAPI + Jinja2, Deno + esbuild,
and Adapter Web Components. This is the first slice; design tokens and
GNOME-inspired visual details are provisional, not a finished design system.

## Run

Requires uv, Deno, and the Adaptive UI skill source (normally installed beside
`automata-web-dev`). Create a project copy; do not build inside installed skills.
Resolve the following helper path against the web-dev skill directory:

```sh
python scripts/create.py --output /path/to/owned/webapp
```

Use `--adaptive-ui /path/to/automata-adaptive-ui` for a non-sibling installation.
The helper refuses an existing destination and records absolute file-URI imports
in the copied `deno.json`. Keep the selected Adaptive UI source available. Then
from the **new project directory**:

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
      tokens/index.ts         # Typed scales and application theme overrides
      tokens/index.html       # /design/tokens/: roles, swatches, resolved values
      tokens/page.ts          # Reads the library's semantic token definitions
      components/index.html   # /design/components/: live local examples
      components/index.ts     # Application composition of library components
      components/counter.ts   # App-local counter, not a library definition
browser/base.js               # Generated output, ignored by Git
scripts/build.ts              # Deno-driven esbuild build/watch
```

Only explicit page routes and `/browser/` are public. Template sources are
not mounted, and underscore naming is a convention, not access control.
No source maps are emitted. The component's count is browser-local and
resets on page navigation; no database or API interaction is implied.

## Shared foundation

This example imports the maintained Adaptive UI `Base`, `Button`,
`Card`, `Form`, `Chat`, and semantic tokens through the Deno import map. `Base` extends
Adapter; npm dependencies use the pinned Adapter JSR distribution and
Edictor validation used by the catalog. esbuild aliases mirror the import
map and resolve dependencies from this example's local `node_modules`.

This avoids duplicating Adaptive UI's foundation. The bundled template's aliases
resolve to a sibling Adaptive UI skill; [the copy helper](../../scripts/create.py) rewrites them when
creating a project elsewhere. This is a source dependency, not a portable published
browser package: independent distribution requires deliberately packaging that
library. The existing library uses `.js` imports for `.ts` files, so its established
Deno sloppy-imports option is retained.

## Design direction

The [GNOME HIG](https://developer.gnome.org/hig/) primarily guides native
GTK/libadwaita applications. This example borrows UX principles for the browser,
not native widgets or a claim of native HIG compliance:

- [Design principles](https://developer.gnome.org/hig/principles.html): prioritize
  the user's next action, keep text concise and disclose secondary detail as needed.
- [Accessibility](https://developer.gnome.org/hig/guidelines/accessibility.html):
  review short descriptive names, keyboard use, large text and high contrast.
- [Adaptiveness](https://developer.gnome.org/hig/guidelines/adaptive.html): start
  narrow, preserve functionality and constrain wide content with maximum widths.

These references inform review; a blue palette alone does not establish alignment.
The typed hierarchy below separates palette choices from semantic intent and
component roles. App theme choices stay in `themePalette`, not component internals.
No dark-mode preference or accessibility certification is implied.

Token/component documentation lives at `/design/tokens/` and
`/design/components/`. The latter demonstrates Button disabled attributes,
Card variants, Form submit/update/reset, and themed/sized sample Chat history.
Chat remains disconnected: no transport, agent requests or simulated replies.

## Typed color hierarchy

Adaptive UI's `paletteEntries` owns exactly the 45 colors/names from the
[official GNOME palette](https://developer.gnome.org/hig/reference/palette.html).
That reference intends them for icons and illustrations; this app deliberately
chooses them for UI primitives, not native compliance. Canonical keys are the nine
families `blue/green/yellow/orange/red/purple/brown/light/dark`, each with shades 1–5.
The former mixed/invented keys and default colors are an approved breaking change.

`semanticColorRoles.color` selects canonical entries or explicitly separate derived
`colorEffects`, retaining the useful `--aui-*` override names. Transparency/shadow
are not extra official swatches: clear uses the CSS keyword and shadows derive an
official entry plus opacity. Component roles map to semantic intent. `tokens` still
provides CSS values; nested `palette` uses only canonical family/shade keys. `@adaptive/colors` exposes the DOM-free color catalog;
`/design/tokens/` consumes it rather than maintaining a second role list.

This app's `themePalette`, `appColorRoles`, and alternate Chat choices reference
palette entries. Page roles stay app-owned. TypeScript applies theme variables
when the browser module loads; HTML styles contain no copied color fallbacks.
The interactive demo requires JavaScript; without it, native browser colors apply.
Legacy resolved values are a page-load snapshot, not a live theme editor.
The small Theme selections below refresh when its mode toggle is used.

## Small scoped Theme

`<ui-theme mode="light|dark">` wraps this application's light DOM. Typed
`themeTokens` select shared palette entries; the Theme replaces one scoped sheet
on mode changes without recreating children. `Theme.setStyleFactories()` receives
trusted component-owned paint factories for explicitly registered tags. This app
supplies Button (`ui-button`), Card (`ui-card`) and its page-owned `base.css.ts`;
that page stylesheet is not the library `Base` component or a Base.css broadcast.

Generated Theme-path paint contains concrete colors and rem-based `clamp()` values,
not CSS variables. With a16px root, body16→18px and main heading28→40px interpolate
across viewport600→1200px and clamp outside those bounds. Root text sizing still
scales rem bounds; this is not a complete large-text/layout repair.

This is **not full library CSS-variable removal**. Legacy Adapter styles, public
`tokens`, app overrides, Form/Chat and Chat sizing remain. Form and Chat are kept
as light presentation islands; do not claim complete dark catalog coverage.
Only one application wrapper in document light DOM is supported: no nested Theme
or automatic ShadowRoot styling. Scope+tag rules beat legacy tag rules; stronger
app/instance selectors, inline styles or `!important` can win. No universal override
priority, OS preference integration or complete WCAG/native-HIG claim is implied.

The library owns component definitions and schemas. Web-dev owns page routes,
composition and app overrides; the counter remains application-local. Button's
`disabled` data is boolean; its attribute follows native presence semantics
(`disabled="false"` still disables). Form's `aui-form-submit` event bubbles and
crosses containing ShadowRoots without clearing drafts. Chat presentation uses
`--aui-message-agent-surface/text`, `--aui-message-user-surface/text` and
`--aui-chat-width/height/min-height/font-size`; overrides do not change send gates.
