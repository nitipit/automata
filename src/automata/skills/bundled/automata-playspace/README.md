# Playspace components

Maintained reusable **TypeScript** components live in `lib/`; the optional
[starter](starter/README.md) is thin JavaScript page composition. Browser-injected
trusted experimental drafts may remain JavaScript. Adaptive UI owns Base, Button,
Card, Form, semantic tokens and public Edictor primitives; Playspace imports only
its public `adaptive-ui.js` exports, never its private component/library paths.

## Build boundary

```sh
# PUBLIC is an approved absolute public-safe website root, outside skill source.
python <playspace-skill>/scripts/build.py --runtime-root "$PUBLIC" --validate
# Copied inputs: --ui-source <ui-skill> --router-source <message-router-tool>.
```

Existing Python, Deno, Node >=20.19 and Adaptive UI's locked cached dependencies
(including esbuild 0.25.11) are required. No downloads, installs, browser/server
launch or source mutation. The builder copies inputs to a private temporary
workspace, builds **one shared** `lib/adaptive-ui.js`, typechecks maintained TS and
transpiles Playspace TS into adjacent ES JS modules. It publishes compiled modules
and starter assets, source-driven Router browser modules and `catalog.json` only
after successful checks. No foundation/runtime rebundling,
plugin loader, schema exporter or framework. Build-only `adaptive-ui.d.ts` resolves
types through the sibling **public entry**; it is not a runtime compatibility shim.
The current focused check uses TypeScript's non-strict baseline with explicitly
typed wire/state/component interfaces, not a declaration that arbitrary JSON is
safe. Edictor owns runtime admission regardless of compile-time typing.

The public root contains only public JS/HTML/CSS and the descriptive JSON catalog. Source TS, tests, build inputs, credentials,
profiles and task records stay outside it. Public assets can be copied while an
existing page is open; applying updated custom elements requires a new page realm
and does not promise preservation of in-memory drafts. Preserve the draft before
an authorized reload. Existing unrelated public assets are not deleted.

## Canonical definitions

- `lib/types.ts`: wire payloads, history vs component IDs, component interfaces,
  Form props/state/submission and ChatSnapshot v2 types.
- `lib/contracts.ts`: executable component/event envelopes, safe IDs/targets,
  serializable JSON and bounded validation errors. **No arbitrary CSS selectors.**
- `lib/content.ts`: ps-text `{text:string}` and ps-json `{value:JSON}` props.
- `lib/form.schema.ts`: ps-form props, full answer validation, readonly state,
  `form-submit` detail, revision construction. `lib/form-history.ts` checks prior
  component/field/answer links before construction, not merely before caching.
- `lib/form.ts`: component controls/styles/listeners and supported event validator.
- `lib/chat.schema.ts`: ps-chat labels and `validation-feedback` detail validator.
- `lib/chat-state.ts`: complete candidate validation and inert event records.
- `lib/registry.ts`, `lib/render.ts`: trusted imports and **one component path**.
- `lib/playspace.ts`: public exports and `registerPlayspace()`; catalog tags remain
  aui-button/aui-form, Playspace tags ps-chat/ps-text/ps-json/ps-form.

These maintained definitions are the agent contract source. Compile to JS for the
browser; do not invent schemas in a page or reinterpret rejected values.

### Public contract discovery

The builder always generates `catalog.json` from `lib/registry.ts` and root
`ps-chat` metadata, with component/root names, canonical contract pointers, public
compiled source links, supported event names and validated examples. Metadata lives
beside each definition; event names come from its executable `events` map. Every
example is admitted by the existing component/event/state validators using the
real shared Edictor bundle before publication. No handwritten parallel schema,
JSONSchema exporter, live user-state inspection or permission grant is involved.

Fetch/read the public catalog, follow its `sources` references, and use the
component-owned validator when producing a reply. Example IDs/state are artificial;
choose unique IDs and valid existing targets for the actual interaction. Event
examples expose prerequisite state for validation, not authority to manufacture a
submission or perform an action. `ps-chat` is a root with settings and
`validation-feedback`, **not** a renderable content component. Unknown component,
event and instance names remain rejected. `generateCatalog()` is also exported
for trusted composition; custom definitions may add the same optional metadata.

## Components and events

All rendered content has one envelope:

```js
{ type: "component", data: {
  name: "ps-text", id: "text-123", props: { text: "Hello" }
} }
{ type: "component", data: {
  name: "ps-json", id: "json-123", props: { value: { note: "Literal JSON" } }
} }
{ type: "component", data: { name: "ps-form", id: "form-123", props: {
  title: "Choose a direction", submitLabel: "Submit complete answers",
  fields: [{ name: "goal", kind: "text", label: "Goal", required: true }],
  initialValues: { goal: "Explore" }, revision: null
} } }
```

Component IDs match `[a-zA-Z][a-zA-Z0-9_-]{0,127}`, exclude reserved names and must
be unique across history **and** the root ps-chat. They remain stable on restore.
History wrappers `{id,role:'user'|'agent',content}` are local display history only;
the history ID is not the component ID or a model-context/delivery identifier.
Imported registry definitions own props/state/events/construction. Unknown names
are rejected; message strings/JSON/cache cannot register executable code.

Interaction payloads are distinct from rendered components:

```js
{ type: "event", data: {
  name: "form-submit", target: "ps-form#form-123", detail: {
    submissionId: "local-submission-id", previousSubmissionId: null,
    values: { goal: "Explore" }
  }
} }
```

The component locally dispatches `CustomEvent('playspace-event', {detail:payload,
bubbles:true,composed:true})`; actual native `event.target` is the emitting DOM
object. The wire `target` is our safe tag+ID convention resolved through the
registered instance map, **never** querySelector/eval or effect authorization.
Supported event names and detail validators belong to the target component.
Unknown names/targets/details fail before persistence/routing. Incoming events
validate and persist inertly; they do not trigger a component action. Local Form
editing and revision creation never route. `ps-chat` routes accepted explicit
interactions through `CustomEvent('agent-message', {detail:completePayload})`.
The page passes that payload unchanged to transport and owns persistence wiring.

Form submission requires every field, including optional blanks, and makes the
original readonly. Detail contains only submissionId/previousSubmissionId/values;
selector identifies the instance, no redundant messageId/componentName. Revise
creates a new ps-form ID, complete prior answers and unchanged field contract;
props.revision retains `{originComponentId,previousSubmissionId}`. Explicit
correction emits another complete validated submission. Neither local record nor
transport receipt proves remote processing; correction cannot undo external effects.

## Chat API / lifecycle

Register once with `registerPlayspace()` before mounting. `addMessage(role,content)`
is local component display, `receiveMessage(payload)` validates components or inert
events, `sendContent(content)` is an explicit component send. Composer emits ps-text
with a stable ID; `markSent()` logs that same component and clears only unchanged
composer text, not text typed while dispatch was pending. Connection/busy/pending
gates disable sends. Invalid reply preserves last-good history and ends local
pending state, never silently retries or repairs.

An explicit **Send validation feedback** action emits once per failure:

```js
{ type: "event", data: { name: "validation-feedback", target: "ps-chat#chat-root",
  detail: { contract: "canonical source pointer", fields: { revision: "safe hint" } }
} }
```

Only known canonical contracts and bounded safe field hints validate. Rejected
values, raw exceptions, stacks and credentials are not sent. Transport replacement
clears the action. No automatic repair retry.

`snapshot()` returns v2 settings/history/composer/pending evidence/componentStates
keyed by **component ID**, plus a separate `events` array of complete inert event
payloads. Events are not raw rendered content and are never replayed. `restore()`
validates the whole candidate before constructing elements, then replaces handles;
it disconnects live state and marks pending interrupted/uncertain, not queued.
Invalid snapshots retain the last-good view. `dispose()` retires handles/listeners;
late client generations and retired component callbacks cannot alter/send/revise
current history. DOM movement alone is not retirement.

## Verification and limits

`--validate` checks maintained TS and runs focused Node tests against the real
compiled Adaptive UI/Edictor exports. To rerun tests on built output:

```sh
PLAYSPACE_LIB="$PUBLIC/lib" PLAYSPACE_CATALOG="$PUBLIC/catalog.json" \
  node --experimental-vm-modules --test <playspace-skill>/tests/*.test.mjs
```

The VM-module flag is used only by the narrow actual-starter orchestration check
(Restore/explicit memory provisioning supersede a delayed paired Connect). Fakes
exercise admission/lifecycle, not actual DOM rendering or native router
acceptance. Browser/keyboard/responsive/reload/live verification belongs to the
preview owner. No attachment bytes, streaming, service worker, backup service,
automatic external-action rollback or v1 migration.
