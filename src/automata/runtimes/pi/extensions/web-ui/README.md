# Browser UI tools

Loaded by Automata browser mode into its native Pi RPC process. Requires that
host's `AUTOMATA_WEB_CONNECTOR_URL` and separate `AUTOMATA_WEB_CONNECTOR_TOKEN`;
never put secrets in tool arguments. Pi supplies typebox; no new npm dependency
or connection starts in the extension factory. With valid host configuration and
`web_ui_execute` active, a compact Pi prompt section orients the agent automatically.
The bundled [Web UI skill](../../../../skills/automata-web-ui/SKILL.md) is added
through native skill discovery in source and Python-package layouts. A standalone
copy of just this extension needs that skill installed separately; no global skill
or configuration is changed automatically.

1. `web_ui_subscribe({name:"answer:chosen",correlationId:"question-1"})` before
   enabling input.
2. `web_ui_execute` accepts an async JS **function body**, with `bridge` and an
   execution-local `ui` context:
   ```js
   const button = document.createElement('button');
   button.textContent = 'Yes';
   button.addEventListener('click', () => {
     button.disabled = true;
     bridge.emit('answer:chosen', {
       correlationId:'question-1', blockId:ui.blockId, answer:'yes'
     });
   }, {once:true});
   ui.root.append(button);
   return {blockId:ui.blockId};
   ```
3. `web_ui_wait_event({subscriptionId:"<returned id>",timeoutMs:30000})` explicitly
   consumes one event; arbitrary DOM changes are not automatically observed.
4. `web_ui_unsubscribe` releases the queue; use JS to remove unneeded listeners.

`ui.root` lazily creates one stable inline block inside the native assistant
message owning this execute toolCall. Before running the JS body, execution waits
for that exact owner (at most half timeoutMs, capped at1s). Missing, inactive or
ambiguous ownership fails explicitly before the body; no fallback to latest reply
or automatic retry. `ui.blockId` and `ui.toolCallId` identify the block. Plain JS calls
create no empty block. Create the initial root before returning, and await initial
asynchronous rendering. Settlement seals **first** root creation, including after
errors: deferred callbacks cannot create a previously unused managed block. Already
materialized roots remain available to later event handlers. This lifecycle guard
is not a sandbox and does not restrict arbitrary full-page JavaScript.
Materialized identity is saved as tool-result `details.ui`,
including observable caught errors. Reload/resume shows historical UI inactive:
**no JavaScript replay or DOM-state restoration**. Same-page blocks may remain
interactive while their handlers/subscriptions remain valid.

Use arbitrary HTML, Web Components, JS, semantic event names and JSON payloads;
there is no widget schema. Code has **full page privileges**, not a sandbox. IDs
and roots are layout/ownership conventions. `bridge.state` retains page-local
values/functions. Events are application input, not authorization or secretly
authored human prompts. Return small JSON values; output above 48 KiB is omitted.

Queues bind to the exact browser connection; they never migrate/replay after
disconnect. Optional correlationId matches data.correlationId exactly. One waiter
per subscription; wait timeout leaves it installed. Stop/disconnect cancels queues;
shutdown aborts local waits and best-effort releases them. No implicit retries:
timeout/cancellation/disconnect may follow real effects or consumed events and do
not stop/undo JS. `effects: unknown` is not proof of rollback. Inspect before
repeating a consequential action. See [tools](index.ts) and [HTTP lifecycle](connector.ts).
