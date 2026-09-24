// Public rename contracts; fixture credentials only, no live endpoints or sockets.
import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtemp, mkdir, writeFile} from 'node:fs/promises';
import {dirname, join} from 'node:path';
import {pathToFileURL} from 'node:url';

const root = process.env.AGENT_BROWSER_BRIDGE_TEST_ROOT;
const {default:register} = await import(pathToFileURL(join(root,'message-router/index.ts')));
const {readEndpoint, assertInstalledTool} = await import(pathToFileURL(join(root,'message-router/transport.ts')));
const names = ['message_router','agent_router','agent_browser_bridge'];

test('default exposure uses one canonical name and explicit compatibility selections survive', () => {
  for (const [initial, expected] of [
    [[], ['message_router']],
    [['read', ...names], ['read','message_router']],
    [['read','message_router','agent_router'], ['read','message_router']],
    [['read','agent_router'], ['read','agent_router']],
    [['agent_browser_bridge'], ['agent_browser_bridge']],
  ]) {
    let active = [...initial];
    const tools = new Map(), handlers = new Map();
    register({
      registerTool: tool => tools.set(tool.name,tool),
      on: (name,handler) => handlers.set(name,handler),
      getActiveTools: () => active,
      setActiveTools: value => {active = value;},
    });
    assert.deepEqual([...tools.keys()],names);
    handlers.get('session_start')({}, {ui:{setStatus(){}},sessionManager:{getSessionId:()=> 'fixture'}});
    assert.deepEqual(active,expected);
    assert.equal(tools.get('message_router').label,'Message Router');
    assert.ok(tools.get('message_router').promptGuidelines.some(line=>line.includes('Use message_router action=open')));
    handlers.get('session_shutdown')();
  }
});

test('endpoint selection preserves historical state and explicit identity precedence', async () => {
  const cwd = await mkdtemp(join(root,'endpoint-selection-'));
  const envNames = ['AUTOMATA_MESSAGE_ROUTER_ENDPOINT','AUTOMATA_AGENT_ROUTER_ENDPOINT','AUTOMATA_AGENT_BROWSER_BRIDGE_ENDPOINT'];
  const saved = envNames.map(name => process.env[name]);
  for (const name of envNames) delete process.env[name];
  async function endpoint(path,participant) {
    await mkdir(dirname(path),{recursive:true});
    await writeFile(path,JSON.stringify({v:2,wsUrl:'ws://127.0.0.1:9999/ws',
      publicUrl:'http://127.0.0.1:9999',participant,kind:'agent',token:'fixture-only'}));
    return path;
  }
  try {
    await endpoint(join(cwd,'.agents/var/tools/agent-router/endpoints/participants/agent.json'),'historical');
    // No namespace-based discovery: only the documented historical default is used.
    await endpoint(join(cwd,'.agents/var/tools/message-router/endpoints/participants/agent.json'),'unselected');
    assert.equal((await readEndpoint(cwd)).participant,'historical');
    process.env.AUTOMATA_AGENT_ROUTER_ENDPOINT = await endpoint(join(cwd,'old-env.json'),'old-env');
    assert.equal((await readEndpoint(cwd)).participant,'old-env');
    process.env.AUTOMATA_MESSAGE_ROUTER_ENDPOINT = await endpoint(join(cwd,'new-env.json'),'new-env');
    assert.equal((await readEndpoint(cwd)).participant,'new-env');
    const explicit = await endpoint(join(cwd,'explicit.json'),'explicit');
    assert.equal((await readEndpoint(cwd,explicit)).participant,'explicit');
    assert.equal((await readEndpoint(cwd,'explicit.json')).participant,'explicit');
    process.env.AUTOMATA_MESSAGE_ROUTER_ENDPOINT = join(cwd,'missing.json');
    await assert.rejects(readEndpoint(cwd),/endpoint unavailable.*missing.json/);
    await assert.rejects(readEndpoint(cwd,'missing-explicit.json'),/endpoint unavailable.*missing-explicit.json/);
    // Legacy alias still selects only its own endpoint knob/default.
    const legacy = join(cwd,'bridge.json');
    await writeFile(legacy,JSON.stringify({wsUrl:'ws://127.0.0.1:9999/ws',publicUrl:'http://127.0.0.1:9999',controlToken:'fixture-only'}));
    process.env.AUTOMATA_AGENT_BROWSER_BRIDGE_ENDPOINT = legacy;
    assert.equal((await readEndpoint(cwd,undefined,true)).controlToken,'fixture-only');
  } finally {
    envNames.forEach((name,index) => {
      if (saved[index] === undefined) delete process.env[name]; else process.env[name] = saved[index];
    });
  }
});

test('v1 artifact preflight accepts the renamed installation and historical packages', async () => {
  for (const name of ['message-router','agent-router','agent-browser-bridge']) {
    const cwd = await mkdtemp(join(root,'artifact-preflight-'));
    await assert.rejects(assertInstalledTool(cwd),/artifacts are missing/);
    for (const file of ['agent_browser_bridge.py','browser/client.js','browser/page.js']) {
      const path = join(cwd,'.agents/tools',name,file);
      await mkdir(dirname(path),{recursive:true});
      await writeFile(path,'fixture');
    }
    await assertInstalledTool(cwd);
  }
});
