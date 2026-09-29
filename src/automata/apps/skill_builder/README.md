# Skill Builder

Canonical agent content lives in `skills/*/SKILL.md` and linked `references/*.md`.
The landing shows the **entire SKILL.md as literal source**, including frontmatter,
fences and final newline. Its Mermaid fences remain code. References are rendered
with native Engrave Markdown, local highlighting and Mermaid diagrams. There is no
separate Overview source and no router connection or snippet execution feature.

## Run

With Engrave 3.2.6 already cached:

```sh
PYTHONPATH=src uv run --offline --no-project --with engrave==3.2.6 \
  python -m automata.apps.skill_builder.cli serve message-router --port 8788
```

Open `http://127.0.0.1:8788/message-router/`; references have ordinary `.html` URLs.
The home catalog is `/templates/index.html` in both single-skill and `--all`
modes; there is no root entry or redirect. Single mode still exposes only the
selected skill's content. The maintained catalog checks each listed URL once per
connection using a same-origin GET with a five-second timeout and no redirects.
Only successful entries become keyboard-accessible links. Non-OK, network and
timeout results read “Unavailable in this preview,” without claiming a cause;
reload to retry. Pending/unavailable links have no `href`, are `aria-disabled`, and
have an associated status. Disconnect aborts checks and ignores stale responses.
No polling, service discovery, additional content exposure or selection changes
occur. JavaScript is required to enable catalog links.

`server.py` checks reviewed bundles, prints the exact
native command and owns its subprocess/temporary output. It contains no renderer,
HTTP proxy, private factory hooks or custom watcher. Anatomy links this separate
site and never starts it.

Native CLI equivalent for this maintained one-skill catalog, from the checkout:

```sh
SOURCE="$PWD/src/automata/apps/skill_builder"
OUTPUT="$(mktemp -d)"
trap 'rm -r -- "$OUTPUT"' EXIT
PAGES='(configure|connect|discover|send|failures)'
ASSETS='templates/((components|lib)/[^/]+\.js|[^/]+\.css\.js|licenses/[^/]+\.txt)'
PUBLIC="(templates/index\.html|message-router/(|index\.html|references/$PAGES\.html)|skills/message-router/(SKILL\.md|references/$PAGES\.md)|$ASSETS)"
uv run --offline --no-project --with engrave==3.2.6 engrave server "$SOURCE" "$OUTPUT" \
  --host 127.0.0.1 --port 8788 \
  --copy "^($ASSETS|skills/message-router/SKILL\.md)\Z" --exclude "^(?!$PUBLIC\Z)"
```

Use `engrave build` with the same source/output/copy/exclude arguments, without
host/port, for a one-shot build. The app wrapper expands exact selected filenames
rather than the concise maintained-layout patterns above. Never serve a repository
root or place private files in the public asset directories.

## Authoring and native semantics

- Tiny `message-router/*.html` and `references/*.html` entry wrappers inherit the
  shared layout and name canonical Markdown; they contain no tutorial prose.
  Add ordinary entries/navigation and a catalog link when adding another skill.
- Native `--copy` publishes selected `SKILL.md` files unchanged. `raw-skill.js`
  fetches the same-origin asset into `code.textContent`, with bounded failure UI.
  Native copy events refresh the source view; references use native Markdown
  dependency rebuilds. No staged authoring copies or second watcher exist.
- **References are trusted authored templates:** native `markdown(path)` evaluates
  Jinja even inside code fences and permits authored raw HTML. Current reference
  snippets are verified unchanged, but arbitrary `{{ ... }}` / `{% ... %}` examples
  may be transformed or fail. The raw SKILL source view does not have this limit.
  Do not feed untrusted Markdown to native template rendering. Frontmatter is not
  stripped or hidden if present in a rendered reference.
- **Local development server, not hardened hosting:** native Host/Origin handling
  is permissive; no CSP/error redaction is added. Native `/docs` and `/openapi.json`
  remain available, and template errors can show tracebacks/source paths. In 3.2.6,
  excluded paths are denied with generic500 because native exception details are
  not JSON-serializable; this is not a promised404. Private templates, Python files
  and traversal requests are tested as denied, not served.
- Restart after changing selection, links or shared excluded templates. Markdown
  body edits and copied assets refresh natively. A failed native rebuild may stop
  its watcher: fix the source and restart. Keep output temporary and loopback-only.

All three reviewed local bundles (Adaptive UI, Mermaid, Prism.js) and exact
notices ship in `templates/lib` and `templates/licenses`; serving needs no download.
The pinned Prism 1.30.0 grammars, official line-numbers plugin, license, hashes and
rebuild recipe are recorded in
[its provenance](templates/licenses/prism-PROVENANCE.txt). JS/JSON/Bash/Python/YAML
fences and aliases, plus the full Markdown source view, are highlighted. Unknown
languages remain literal but receive the same official line-number gutter. Inline
code and rendered Mermaid diagrams are not numbered. Numbers are CSS counters in
an `aria-hidden`, unselectable gutter; native code selection remains unchanged.
Code uses horizontal scrolling (no wrapping), preserving tabs and final newlines.
Plugin CSS belongs to the CodeExample Adapter stylesheet, not a head style/CDN.
Reconnect and asynchronous source updates reset tokens/gutters before highlighting.
If Prism changes whitespace (notably NBSP), that block falls back to exact literal
text with official line numbers rather than changing the authored source.

`export-agent NAME --output DIR` writes Markdown only. The normal installer maps
canonical `skills/message-router` to `automata-message-router` directly, without
website dependencies or a duplicate packaged skill. Serving never installs/syncs.

## Verify

Tests cover native CLI builds, exact source copying, real Chrome single/all source
and reference refresh, current snippet fidelity, native limitations, local request
boundaries, highlighting/themes, and wheel/sdist/disposable skill installation.
The previous adapter's literal-reference, raw-HTML sanitization, strict Host/Origin
and traceback-redaction assertions are deliberately replaced by explicit native
characterization—not claimed as equivalent guarantees.
