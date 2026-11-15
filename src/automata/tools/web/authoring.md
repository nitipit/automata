# Inline UI authoring

Use this as the async function body of `web_ui_execute`. Import the locally
served canonical ESM entry; do not load a CDN, re-bundle Adapter/ArrowJS, or make a
second theme store. `ui.root` is owned by this exact assistant tool call. Existing
history stays inactive: never reconstruct it by replaying historical JavaScript.

```js
const { Card, Button, Markdown, Base, palette, setTheme } =
  await import('/assets/ui.js');

const card = new Card();
const text = new Markdown();
text.source = '## Local example\n\nA shared **themed** component.';
const button = new Button();
button.textContent = 'Show details';
button.addEventListener('click', () => {
  text.source = '## Details\n\nThe existing button and its handlers stay alive.';
});
card.append(text, button);
ui.root.append(card);
setTheme(card, { accent: 'violet' }); // Partial scope inherits the app mode/roles.

// Extend the real Adapter-based base: shared structure, literal instance colors.
class AccentNote extends Base {
  themedStyle(theme) {
    return `background:${theme.roles.accentSoft};border-color:${theme.roles.border};`;
  }
}
AccentNote.css = 'display:block;padding:.75rem;border:1px solid;border-radius:.5rem;';
if (!customElements.get('example-accent-note')) AccentNote.define('example-accent-note');
const note = document.createElement('example-accent-note');
note.textContent = `Chart palette example: ${palette.blue[500]}`;
card.append(note);
return { blockId: ui.blockId };
```

The same `/assets/ui.js` exports `Adapter`, `css`, ArrowJS `reactive`, `watch`,
`nextTick`, `html`, the runtime `culori` namespace, `appTheme`, `createTheme`,
`setTheme`, `clearTheme`, `bindTheme`, and the five initial components. `CodeBlock`
takes `.source`/`.language` or `.setCode(source, language)`; never interpolate
untrusted source into attributes or execute code to highlight it. `Markdown`
takes `.source`; raw HTML is disabled and fenced code uses `CodeBlock`.

`setTheme(element, partial)` scopes the host and descendants across ShadowDOM;
`clearTheme(element)` restores nearest inheritance. The returned reference's
`.set(partial)` replaces overrides, so omitted fields restore inheritance. Explicit
`component.theme = createTheme(...)` affects that component; set it to `undefined`
to return to nearest scope. `appTheme.set({mode:'dark'})` changes the shared app;
prefer a local scope unless a global theme change was requested. Roles accept
opaque literal colors and are serialized to sRGB; CSS variables are not used.
Palette shades are not universally accessible against each other.

Use `Component.css` only for shared structure and the `themedStyle(theme)` hook
for resolved instance colors. If overriding lifecycle callbacks, call the Base
callbacks; Base handles theme subscription/sheet cleanup without replacing child
DOM. Manual `bindTheme` callers own its returned cleanup. ArrowJS1.0.6 standalone
`watch` has a queued-stop edge case: a stopped, already queued effect must read no
reactive inputs; Base's binding guards this automatically.

For semantic events to the agent, subscribe with `web_ui_subscribe` **before**
enabling controls, then use `bridge.emit(name, {blockId:ui.blockId, ...})`; preserve
correlation and release the subscription. A browser click is not a human prompt.
Full-page JavaScript has page privileges and is **not sandboxed**.
