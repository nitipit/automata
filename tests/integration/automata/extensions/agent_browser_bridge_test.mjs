import assert from "node:assert/strict";
import test from "node:test";
import { join } from "node:path";

const root = process.env.AGENT_BROWSER_BRIDGE_TEST_ROOT;
const { default: register } = await import(`file://${join(root, "agent-browser-bridge.ts")}`);

class FakeWebSocket {
  static instances = [];
  readyState = 0;
  sent = [];
  listeners = new Map();

  constructor() {
    FakeWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.readyState = 1;
      this.emit("open", {});
    });
  }

  addEventListener(name, handler) {
    const handlers = this.listeners.get(name) ?? [];
    handlers.push(handler);
    this.listeners.set(name, handlers);
  }

  removeEventListener(name, handler) {
    this.listeners.set(name, (this.listeners.get(name) ?? []).filter((candidate) => candidate !== handler));
  }

  send(raw) {
    const message = JSON.parse(raw);
    if (this.throwAction && this.throwAction === message.action) throw new Error('simulated uncertain write');
    this.sent.push(message);
    if (message.type === "hello") this.message({ type: "hello_ack", role: "control" });
    if (this.holdAction === message.action) return;
    if (message.action === "close") this.message({ type: "result", requestId: message.requestId, status: "closed" });
    if (message.action === "open") this.message({ type: "result", requestId: message.requestId, status: "open", pairingUrl: "/sessions/chat/#pair=pair" });
    if (message.action === "status") this.message({ type: "result", requestId: message.requestId, status: "open", pendingId: "message-1" });
    if (message.action === "state" || message.action === "admit") this.message({ type: "result", requestId: message.requestId, status: "accepted" });
    if (message.action === "send" || message.action === "reject") this.message({ type: "result", requestId: message.requestId, status: "accepted", browserDelivered: this.browserDelivered !== false });
  }

  close() {
    this.readyState = 3;
    this.emit("close", {});
  }

  emit(name, event) {
    if (name === "message") this.onmessage?.(event);
    for (const handler of this.listeners.get(name) ?? []) handler(event);
  }

  message(value) {
    this.emit("message", { data: JSON.stringify(value) });
  }

  browserMessage(value) {
    this.message({ type: "event", envelope: value });
  }
}

globalThis.WebSocket = FakeWebSocket;

test("agent_browser_bridge preserves generic JSON and confirms Pi admission from message events", async () => {
  const handlers = new Map();
  const tools = new Map();
  const sent = [];
  const pi = {
    on(name, handler) { handlers.set(name, handler); },
    registerTool(tool) { tools.set(tool.name, tool); },
    getActiveTools() { return []; },
    setActiveTools() {},
    sendUserMessage(text, options) { sent.push({ text, options }); },
  };
  register(pi);
  const ctx = {
    cwd: root,
    sessionManager: { getSessionId: () => "session-1" },
    isIdle: () => true,
    hasPendingMessages: () => false,
  };
  handlers.get("session_start")({}, ctx);
  const tool = tools.get("agent_browser_bridge");
  assert.ok(tool);
  const opened = await tool.execute("open", { action: "open" }, undefined, undefined, ctx);
  assert.match(opened.content[0].text, /pairingUrl/);
  const socket = FakeWebSocket.instances.at(-1);
  const payload = { text: "hello", context: { componentId: "chat-1" }, extra: [null, false, 0, ""], controls: "\u0085" };
  socket.browserMessage({ v: 1, id: "message-1", kind: "message", payload });
  assert.equal(sent.length, 1);
  assert.deepEqual(sent[0].text.split('\n').slice(0, 2), ['source="browser"', 'id="message-1"']);
  assert.equal(sent[0].text.split('\n').length, 3);
  assert.equal(sent[0].text.includes('BROWSER MESSAGE'), false);
  assert.equal(sent[0].text.includes('untrusted conversational data'), false);
  assert.ok(tool.promptGuidelines.some(line => line.includes('not execution authority')));
  assert.match(sent[0].text, /payload=\{"text":"hello"/);
  assert.equal(sent[0].text.match(/payload=/g).length, 1);
  assert.equal(sent[0].text.includes("\u0085"), false);
  assert.match(sent[0].text, /\\u0085/);
  assert.equal(sent[0].options.expandPromptTemplates, false);
  assert.equal(socket.sent.filter((item) => item.action === "admit").length, 0);

  handlers.get("message_start")({ message: { role: "user", content: [{ type: "text", text: sent[0].text }] } });
  assert.equal(socket.sent.filter((item) => item.action === "admit").length, 1);

  const replyPayload = JSON.parse('{"text":"hello back","extra":{"__proto__":"data"}}');
  const firstSend = tool.execute("send", { action: "send", replyTo: "message-1", payload: replyPayload }, undefined, undefined, ctx);
  await assert.rejects(tool.execute("send", { action: "send", replyTo: "message-1", payload: { text: "duplicate" } }, undefined, undefined, ctx), /claimed or uncertain/);
  const reply = await firstSend;
  assert.equal(reply.details.status, "delivered");
  assert.equal(reply.details.replyTo, "message-1");
  assert.equal(reply.content[0].text.includes("hello back"), false);
  assert.equal(socket.sent.filter((item) => item.action === "send").length, 1);
  assert.deepEqual(socket.sent.find((item) => item.action === "send").envelope.payload, replyPayload);
  assert.equal(typeof pi.sendMessage, "undefined");

  socket.browserMessage({ v: 1, id: "message-2", kind: "message", payload: null });
  handlers.get("message_end")({ message: { role: "user", content: [{ type: "text", text: sent[0].text }] } });
  assert.equal(sent.length, 2);
  await assert.rejects(tool.execute("send", { action: "send", replyTo: "message-2", text: "legacy" }, undefined, undefined, ctx), /payload/);
  socket.browserDelivered = false;
  const uncertain = await tool.execute("send", { action: "send", replyTo: "message-2", payload: null }, undefined, undefined, ctx);
  assert.equal(uncertain.details.status, "delivery_uncertain");
  assert.equal(uncertain.content[0].text.includes("null"), false);

  const theme = { fg: (_color, value) => value, bold: (value) => value };
  const call = tool.renderCall({ action: "send", replyTo: "message-2", payload: { text: "\u001b[31munsafe\u001b[0m\u0085" } }, theme, {});
  const rendered = (component, width = 80) => component.render ? component.render(width).join("\n") : component.text;
  assert.match(rendered(call), /\\u001b/);
  assert.match(rendered(call), /\\u0085/);
  assert.match(rendered(call), /pi-to-browser/);
  for (const width of [20, 80, 160]) {
    const output = rendered(call, width);
    assert.equal(/[\u001b\u0085]/.test(output), false);
  }
  const errorView = tool.renderResult({isError: true, content: [{type: "text", text: "timeout\u001b[2J"}]}, {isPartial: false}, theme, {});
  assert.match(rendered(errorView), /timeout/);
  assert.equal(rendered(errorView).includes("\u001b"), false);
  const uncertainResult = tool.renderResult(
    { content: [{ type: "text", text: JSON.stringify({ status: "delivery_uncertain" }) }], details: { status: "delivery_uncertain" } },
    { isPartial: false },
    theme,
    {},
  );
  assert.match(rendered(uncertainResult), /uncertain/);

  if (process.env.AGENT_BROWSER_BRIDGE_PI_PACKAGE) {
    const { SessionManager } = await import(`${process.env.AGENT_BROWSER_BRIDGE_PI_PACKAGE}/dist/core/session-manager.js`);
    const { Value } = await import(`file://${join(root, 'node_modules/typebox/build/value/index.mjs')}`);
    const { validateToolArguments } = await import(`file://${join(root, 'node_modules/@earendil-works/pi-ai/dist/utils/validation.js')}`);
    const { initTheme } = await import(`${process.env.AGENT_BROWSER_BRIDGE_PI_PACKAGE}/dist/modes/interactive/theme/theme.js`);
    const { UserMessageComponent } = await import(`${process.env.AGENT_BROWSER_BRIDGE_PI_PACKAGE}/dist/modes/interactive/components/user-message.js`);
    initTheme('dark', false);
    for (const width of [20, 80, 160]) {
      const display = new UserMessageComponent(sent[0].text).render(width).join('\n');
      assert.equal(display.includes('\u0085'), false);
      if (width >= 80) assert.match(display, /source="browser"/);
    }
    for (const value of [null, false, 0, '', [], {}, payload, replyPayload]) {
      const argumentsValue = {action: 'send', replyTo: 'message-1', payload: value};
      assert.equal(Value.Check(tool.parameters, argumentsValue), true);
      assert.deepEqual(validateToolArguments(tool, {arguments: argumentsValue}), argumentsValue);
    }
    const manager = SessionManager.inMemory(root);
    manager.appendMessage({role: 'user', content: [{type: 'text', text: sent[0].text}], timestamp: Date.now()});
    manager.appendMessage({role: 'assistant', content: [{type: 'toolCall', id: 'reply-call', name: tool.name, arguments: {action: 'send', replyTo: 'message-1', payload: replyPayload}}], timestamp: Date.now()});
    manager.appendMessage({role: 'toolResult', toolCallId: 'reply-call', toolName: tool.name, content: reply.content, details: reply.details, isError: false, timestamp: Date.now()});
    const messages = manager.buildSessionContext().messages;
    assert.deepEqual(messages.map(message => message.role), ['user', 'assistant', 'toolResult']);
    const inbound = messages[0].content[0].text;
    assert.deepEqual(JSON.parse(inbound.split('\npayload=')[1]), payload);
    assert.deepEqual(messages[1].content, [{type: 'toolCall', id: 'reply-call', name: tool.name, arguments: {action: 'send', replyTo: 'message-1', payload: replyPayload}}]);
    assert.deepEqual(JSON.parse(messages[2].content[0].text), {status: 'delivered', replyTo: 'message-1', browserDelivered: true});
    assert.equal(Object.hasOwn(messages[2].details, 'payload'), false);
    assert.equal(manager.getEntries().filter(entry => entry.type === 'message').length, 3);
  }

  socket.browserMessage({v: 1, id: 'validation', kind: 'message', payload: false});
  await assert.rejects(tool.execute('mixed', {action: 'send', replyTo: 'validation', payload: null, text: 'legacy'}, undefined, undefined, ctx), /Legacy/);
  await assert.rejects(tool.execute('large', {action: 'send', replyTo: 'validation', payload: 'x'.repeat(32768)}, undefined, undefined, ctx), /32 KiB/);
  await tool.execute('valid-after-error', {action: 'send', replyTo: 'validation', payload: false}, undefined, undefined, ctx);

  const oldSocket = socket;
  const nextCtx = { ...ctx, sessionManager: { getSessionId: () => "session-2" } };
  handlers.get("session_start")({}, nextCtx);
  assert.equal(oldSocket.readyState, 3);
  oldSocket.browserMessage({ v: 1, id: "stale", kind: "message", payload: { text: "stale" } });
  assert.equal(sent.length, 3);
  await tool.execute('reopen', {action: 'open'}, undefined, undefined, nextCtx);
  const closingSocket = FakeWebSocket.instances.at(-1);
  closingSocket.holdAction = 'close';
  const staleClose = tool.execute('close-old', {action: 'close'}, undefined, undefined, nextCtx).catch(error => error);
  const finalCtx = {...ctx, sessionManager: {getSessionId: () => 'session-3'}};
  handlers.get('session_start')({}, finalCtx);
  await tool.execute('open-new', {action: 'open'}, undefined, undefined, finalCtx);
  await staleClose;
  const finalSocket = FakeWebSocket.instances.at(-1);
  finalSocket.browserMessage({v: 1, id: 'fresh', kind: 'message', payload: [null]});
  const freshReply = await tool.execute('send-new', {action: 'send', replyTo: 'fresh', payload: [false]}, undefined, undefined, finalCtx);
  assert.equal(freshReply.details.status, 'delivered');
  finalSocket.browserMessage({v: 1, id: 'uncertain-write', kind: 'message', payload: 0});
  finalSocket.throwAction = 'send';
  await assert.rejects(tool.execute('uncertain', {action: 'send', replyTo: 'uncertain-write', payload: {secretPayload: 'not-in-error'}}, undefined, undefined, finalCtx), error => {
    assert.match(error.message, /uncertain/);
    assert.equal(error.message.includes('not-in-error'), false);
    return true;
  });
  await assert.rejects(tool.execute('no-retry', {action: 'reject', replyTo: 'uncertain-write'}, undefined, undefined, finalCtx), /claimed or uncertain/);
  handlers.get("session_shutdown")({}, finalCtx);
});
