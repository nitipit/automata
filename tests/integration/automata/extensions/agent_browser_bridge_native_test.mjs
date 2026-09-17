// Opt-in native Pi regression: in-memory session, local model stub, no network model calls.
import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const pkg = process.env.AGENT_BROWSER_BRIDGE_NATIVE_PI_PACKAGE;
const root = process.env.AGENT_BROWSER_BRIDGE_TEST_ROOT;
const sdk = await import(join(pkg, 'dist/index.js'));
const { createAssistantMessageEventStream } = await import(join(pkg, '../pi-ai/dist/index.js'));

class ControlSocket {
  static latest;
  readyState = 0;
  requests = [];
  listeners = new Map();
  constructor() {
    ControlSocket.latest = this;
    queueMicrotask(() => { this.readyState = 1; this.emit('open', {}); });
  }
  addEventListener(name, handler) {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), handler]);
  }
  removeEventListener(name, handler) {
    this.listeners.set(name, (this.listeners.get(name) ?? []).filter(h => h !== handler));
  }
  emit(name, event) {
    this[`on${name}`]?.(event);
    for (const handler of this.listeners.get(name) ?? []) handler(event);
  }
  message(value) { this.emit('message', { data: JSON.stringify(value) }); }
  send(raw) {
    const request = JSON.parse(raw);
    this.requests.push(request);
    if (request.type === 'hello') this.message({ type: 'hello_ack', role: 'control' });
    else this.message({ type: 'result', requestId: request.requestId, status: 'open',
      pairingUrl: '/sessions/test/#pair=test', browserDelivered: true });
  }
  close() { this.readyState = 3; this.emit('close', {}); }
}
globalThis.WebSocket = ControlSocket;

const model = {
  id: 'fixture', name: 'fixture', api: 'openai-responses', provider: 'fixture',
  baseUrl: 'http://unused.invalid', reasoning: false, input: ['text'],
  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
  contextWindow: 32000, maxTokens: 1000,
};

test('native Pi confirms idle/deferred canonical appends, nextTurn, and busy binding', async () => {
  for (const file of ['agent_browser_bridge.py', 'browser/client.js', 'browser/page.js']) {
    const path = join(root, '.agents/tools/agent-browser-bridge', file);
    await mkdir(join(path, '..'), { recursive: true });
    await writeFile(path, 'fixture');
  }
  await mkdir(join(root, '.agents/var/tools/agent-browser-bridge'), { recursive: true });
  await writeFile(join(root, '.agents/var/tools/agent-browser-bridge/endpoint.json'),
    JSON.stringify({ wsUrl: 'ws://fixture.invalid', publicUrl: 'http://fixture.invalid', controlToken: 'fixture' }));
  let calls = 0, onStream, streamError;
  const settings = sdk.SettingsManager.inMemory({ compaction: { enabled: false }, retry: { enabled: false } });
  const loader = new sdk.DefaultResourceLoader({
    cwd: root, agentDir: join(root, 'agent'), settingsManager: settings,
    additionalExtensionPaths: [join(root, 'agent-browser-bridge.ts')],
    noSkills: true, noPromptTemplates: true, noThemes: true,
    agentsFilesOverride: () => ({ agentsFiles: [] }), systemPromptOverride: () => 'Local fixture.',
    extensionFactories: [pi => pi.registerProvider('fixture', {
      api: model.api, apiKey: 'fixture', baseUrl: model.baseUrl, models: [model],
      streamSimple: () => {
        calls++;
        const stream = createAssistantMessageEventStream();
        const message = { role: 'assistant', content: [{ type: 'text', text: 'fixture reply' }],
          api: model.api, provider: model.provider, model: model.id, stopReason: 'stop', timestamp: Date.now(),
          usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2,
            cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
        queueMicrotask(async () => {
          try { await onStream?.(); } catch (error) { streamError = error; }
          stream.push({ type: 'done', reason: 'stop', message });
          stream.end(message);
        });
        return stream;
      },
    })],
  });
  await loader.reload();
  assert.deepEqual(loader.getExtensions().errors, []);
  const runtime = await sdk.ModelRuntime.create({ authPath: join(root, 'auth.json'),
    modelsPath: join(root, 'models.json'), modelsStorePath: join(root, 'models-store.json'), allowModelNetwork: false });
  const { session } = await sdk.createAgentSession({ cwd: root, agentDir: join(root, 'agent'),
    resourceLoader: loader, modelRuntime: runtime, model, settingsManager: settings,
    sessionManager: sdk.SessionManager.inMemory(root), tools: ['agent_browser_bridge'] });
  try {
    await session.bindExtensions({});
    const tool = session.agent.state.tools.find(t => t.name === 'agent_browser_bridge');
    const execute = args => tool.execute('fixture', args);
    await execute({ action: 'open' });
    let socket = ControlSocket.latest;
    const deliver = (id, payload, delivery) => socket.message({ type: 'event', envelope: {
      v: 1, kind: 'message', id, payload, delivery: { role: 'context', ...delivery },
    } });
    const statuses = id => socket.requests.filter(r => r.action === 'context_result' && r.id === id).map(r => r.status);
    assert.equal(socket.requests.find(r => r.action === 'state').payload.busy, false);
    for (let i = 0; i < 20; i++) {
      deliver(`idle-${i}`, i, { deliverAs: ['immediate', 'steer', 'followUp'][i % 3] });
      assert.deepEqual(statuses(`idle-${i}`), ['queued', 'attached']);
    }
    assert.equal(calls, 0);
    assert.equal(session.messages.filter(m => m.role === 'custom').length, 20);
    assert.equal((await execute({ action: 'status' })).details.queuedContext, 0);

    deliver('old', 'old-selection', { deliverAs: 'nextTurn', slot: 'selection' });
    deliver('latest', 'new-selection', { deliverAs: 'nextTurn', slot: 'selection' });
    onStream = () => {
      deliver('deferred', 'deferred-evidence', { deliverAs: 'followUp', triggerTurn: false });
      assert.deepEqual(statuses('deferred'), ['queued']);
    };
    await session.prompt('exercise nextTurn and deferred append');
    if (streamError) throw streamError;
    assert.equal(calls, 1);
    assert.deepEqual(statuses('deferred'), ['queued', 'attached']);
    assert.ok(session.messages.some(m => m.role === 'custom' && m.content.includes('deferred-evidence')));
    assert.deepEqual(statuses('old'), ['buffered', 'replaced']);
    assert.deepEqual(statuses('latest'), ['buffered', 'attached']);
    assert.equal((await execute({ action: 'inspect_context' })).details.entries.length, 0);
    assert.equal((await execute({ action: 'status' })).details.queuedContext, 0);

    onStream = async () => {
      await execute({ action: 'close' });
      await execute({ action: 'open' });
      socket = ControlSocket.latest;
      assert.equal(socket.requests.find(r => r.action === 'state').payload.busy, true);
    };
    await session.prompt('open a binding during a real running turn');
    if (streamError) throw streamError;
    assert.equal(calls, 2);
    assert.equal(socket.requests.filter(r => r.action === 'state').at(-1).payload.busy, false);
    await execute({ action: 'close' });
  } finally { session.dispose(); }
});
