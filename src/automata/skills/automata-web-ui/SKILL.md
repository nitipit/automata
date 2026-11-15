---
name: automata-web-ui
description: Use when working inside an existing agent-facing Web UI, choosing text or interactive presentation, and authoring, updating or cleaning up UI with the host's tools and shared components. Not for launching a runtime, controlling unrelated websites, or general UI design alone.
---

# Automata Web UI

Work within the running host rather than treating every UI request as a new app.
A Web UI can be a workspace, form, dashboard or conversation; chat is one host,
not the definition of this capability. This guidance adds no permission policy
or limits to the host's JavaScript capabilities.

## Choose the presentation and discover the host

- Use ordinary text for explanations, brief answers and results that need no
  interaction. Add UI when choosing, exploring, editing or visual comparison
  benefits from controls; combine a short explanation with UI when useful.
- Read the current host orientation and exposed tool contracts. Identify the
  active page, available execution/event tools, intended content region, shared
  modules and lifetime of the interaction. Skill availability alone does not
  establish a live host. Reuse the supplied connection; runtime launch/setup is
  a separate task, not an implied step in authoring content.
- Use the host-provided content region by default. A requested host-wide change
  can use the wider page capabilities; a content root is a layout convention,
  not a sandbox. Do not assume every host has assistant messages, `ui.root`,
  `bridge`, or tools named `web_ui_*`.
- Inspect the actual installed exports/source when the host differs. The
  concrete foundation below is served by Automata's browser host; it is not a
  generic API promised by every Web UI.

## Reuse the shared foundation

Automata serves a canonical ESM entry at `/assets/ui.js`: `Adapter`, `css`,
ArrowJS `reactive`, `watch`, `nextTick`, `html`, the runtime `culori` namespace,
`palette`, `appTheme`, `createTheme`, `setTheme`, `clearTheme`, `bindTheme`, `Base`,
`Button`, `Card`, `Field`, `CodeBlock` and `Markdown`. Import that module to share
class identity and stores rather than loading CDN/re-bundled copies or creating
a second app theme. Arbitrary HTML, Web Components and JavaScript remain usable;
the components are a starting point, not a widget schema.

Use `CodeBlock.source`/`.language` or `.setCode(source, language)` for source;
do not execute code to highlight it or interpolate untrusted source into HTML
attributes. `Markdown.source` renders Markdown with raw HTML disabled and fenced
code through `CodeBlock`. Use native semantic controls, associated labels,
keyboard operation, visible focus and clear pending/error/completed states.
Check responsive layout and actual contrast; palette shades are not universally
accessible against each other.

`setTheme(element, partial)` scopes the element and descendants across ShadowDOM;
`clearTheme(element)` restores nearest inheritance. The returned reference's
`.set(partial)` replaces overrides: omitted fields restore inheritance. Explicit
`component.theme = createTheme(...)` affects that component; assign `undefined`
to return to the nearest scope. `appTheme.set({mode:'dark'})` changes the shared
app; prefer a local scope for local content unless an app-wide change is intended.
Theme roles accept opaque literal colors serialized to sRGB, not CSS variables.

Use `Component.css` for shared structure and `themedStyle(theme)` for resolved
instance colors. Call the inherited Base lifecycle callbacks when overriding
them; Base manages theme subscription and stylesheet cleanup without replacing
child DOM. Manual `bindTheme` callers own its returned cleanup. ArrowJS 1.0.6
standalone `watch` has a queued-stop edge case: a stopped, already queued effect
must read no reactive inputs; Base's binding guards this automatically.

## Practical example in Automata's browser host

Use this as the async function body of `web_ui_execute`, whose execution-local
`ui.root` supplies the content region. Other hosts must supply their own region
and execution context; the component and theme APIs are the shared part.
This local-only button updates the page without needing an agent round trip.

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

## Interaction, updates and lifetime

For an interaction that needs the agent, establish the host's event listener or
subscription before enabling the control. Emit a meaningful application event
with a small JSON payload and useful correlation/region identity, then explicitly
receive it through the host's event mechanism. A DOM update alone is not event
receipt. Browser events are application input, not secretly authored human
prompts; interpret the offered action and its payload in context.

Keep existing nodes and handlers when updating a live view; acknowledge input,
show progress and surface failures in the page. Distinguish a live handle from
historical output: reconnection or conversation history does not prove that old
DOM, listeners or subscriptions still exist. Use the current host's documented
live-context lookup and recovery behavior rather than replaying old JavaScript.
The Automata Pi extension's tool definitions own its exact message ownership,
root-creation and inactive-history contracts.

Retain only the page-local state needed for the interaction. On completion or
replacement, remove obsolete listeners, timers and manual reactive bindings,
and release owned event subscriptions. Releasing a queue does not itself remove
DOM handlers. Timeouts and cancelled waits need not undo JavaScript or consumed
events; inspect the current state before repeating consequential changes. Keep
cleanup scoped to the interaction's resources and preserve the user's host.
