# Browser UI tools

Loaded by Automata browser mode into its fresh Pi RPC process. Requires the same
Python host's `AUTOMATA_WEB_CONNECTOR_URL` and **separate**
`AUTOMATA_WEB_CONNECTOR_TOKEN` environment values; never supply secrets as tool
arguments. No installation, server startup, model call or connection occurs in
this extension's factory. Pi supplies `typebox`; no additional npm dependencies.

1. `web_ui_subscribe({name:"answer",correlationId:"question-1"})` **before** enabling input.
2. `web_ui_execute` accepts an async JS **function body**, for example:
   ```js
   const button = document.createElement('button');
   button.textContent = 'Yes';
   button.addEventListener('click', () => {
     button.disabled = true;
     bridge.emit('answer', {correlationId:'question-1', answer:'yes'});
   }, {once:true});
   document.querySelector('#generated-ui').replaceChildren(button);
   return null;
   ```
3. `web_ui_wait_event({subscriptionId:"<returned id>",timeoutMs:30000})` consumes one event.
4. `web_ui_unsubscribe` releases the queue; remove unneeded controls/listeners with JS.

This is general JavaScript with **full page privileges**, not a sandbox or widget
framework. `bridge.state` retains page-local values/functions. Return small JSON
values; output above 48 KiB is omitted. Browser input is data, not authorization.
Queues bind to one browser connection and do not migrate/replay after disconnect.
Wait timeout leaves its subscription installed; one-shot listeners avoid duplicate
human actions. Shutdown aborts local waits and best-effort releases known queues
within a bounded deadline; host Stop/disconnect owns final subscription cleanup.

No automatic retries. After timeout/cancellation/transport failure, JS may still
run or input may already have been consumed. Inspect state before repeating a
consequential action. `effects: unknown` is not proof of failure or rollback.
See [tools](index.ts) and [HTTP lifecycle](connector.ts) for deeper contracts.
