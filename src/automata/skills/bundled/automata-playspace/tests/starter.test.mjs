import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs/promises";
import path from "node:path";
import vm from "node:vm";

/** Real starter orchestration with narrow dependency/DOM fakes, not browser proof. */
test("Restore and Connect honor newest explicit intent before and after cache waits", async () => {
  class Element {
    value = ""; textContent = ""; disabled = false; elements = []; listeners = new Map();
    addEventListener(name, fn) { if (!this.listeners.has(name)) this.listeners.set(name, new Set()); this.listeners.get(name).add(fn); }
    removeEventListener(name, fn) { this.listeners.get(name)?.delete(fn); }
    click() { for (const fn of this.listeners.get("click") ?? []) fn({target:this,preventDefault(){}}); }
  }
  const ids = ["pairing-state", "pairing-code", "target-participant", "pairing-form", "connect-session",
    "forget-pairing", "target-preference-state", "connection", "recovery", "sample-mode", "live-mode",
    "sample-form", "save", "restore", "startup-error"];
  const elements = new Map(ids.map(id => [id, new Element()]));
  elements.get("target-participant").value = "pc1-agent";
  let restorations = 0;
  const chat = Object.assign(new Element(), {interrupt(){},setConnection(){},setAgentBusy(){},setStatus(){},
    snapshot:()=>({}),restore:()=>{restorations++;return true;},addMessage(){},dispose(){},reject(){},receiveMessage(){},markSent(){}});
  const storage = new Map(), connections = [];
  let candidate = null, deferredStatus, holdStatus = false, deferredLoad, holdLoad = false;
  const context = vm.createContext({URL, setTimeout, clearTimeout,
    location:{origin:"http://127.0.0.1:8775",href:"http://127.0.0.1:8775/"},
    document:{querySelector:selector => selector === "ps-chat" ? chat : elements.get(selector.slice(1)),
      getElementById:id => elements.get(id)}, addEventListener(){},removeEventListener(){},
    localStorage:{getItem:key => storage.get(key) ?? null,setItem:(key,value) => storage.set(key,value)},
    fetch:async () => {
      const response = {ok:true,json:async()=>({authenticated:true,participant:"page",expiresAt:100})};
      if (!holdStatus) return response;
      holdStatus = false;
      return new Promise(resolve => { deferredStatus = () => resolve(response); });
    },
  });
  const clientFactory = options => ({
    async connectSession() { connections.push({kind:"session",to:options.to}); options.onState({status:"connected"}); },
    async connect() { connections.push({kind:"token",to:options.to}); options.onState({status:"connected"}); },
    async status() { return {destinations:[{id:options.to,kind:"agent",connected:true}]}; },
    close(){},isConnected:()=>true,
  });
  const fakes = {
    "lib/playspace.js":{registerPlayspace(){},ContractError:class extends Error{},text:value=>value,formContracts:{}},
    "lib/recovery.js":{createCacheRecovery:()=>({flush:async()=>{},load:async()=>{
      if (!holdLoad) return candidate;
      return new Promise(resolve => {deferredLoad=()=>resolve(candidate);});
    },save:async()=>true,dispose(){}})},
    "lib/state.js":{validateStarterSnapshot:value=>value},
    "sample.js":{sampleForm:()=>null,sampleReply:()=>null},
    "router/pi-client.js":{createMessageRouterChatClient:clientFactory},
  };
  const modules = new Map(), stage = path.dirname(process.env.PLAYSPACE_LIB);
  async function load(name) {
    if (modules.has(name)) return modules.get(name);
    const exports = fakes[name];
    const module = exports ? new vm.SyntheticModule(Object.keys(exports), function() {
      for (const [key,value] of Object.entries(exports)) this.setExport(key,value);
    }, {context,identifier:name}) : new vm.SourceTextModule(await fs.readFile(path.join(stage,name),"utf8"), {context,identifier:name});
    modules.set(name,module);
    await module.link((specifier,parent) => load(path.posix.normalize(path.posix.join(path.posix.dirname(parent.identifier),specifier))));
    return module;
  }
  await (await load("index.js")).evaluate();
  const tick = () => new Promise(resolve => setImmediate(resolve));
  await tick();
  try {
    holdStatus = true; elements.get("connect-session").click(); await tick();
    assert.ok(deferredStatus);
    candidate = {version:2,mode:"sample",chat:{}};
    holdLoad = true; elements.get("restore").click(); await tick();
    assert.ok(deferredLoad);
    deferredStatus(); await tick(); await tick(); // cancellation must precede delayed cache load
    assert.equal(connections.length,0);
    deferredLoad(); holdLoad = false; await tick(); await tick();
    assert.match(elements.get("connection").textContent,/SAMPLE/);
    holdStatus = true; deferredStatus = undefined;
    elements.get("connect-session").click(); await tick();
    assert.ok(deferredStatus);
    await context.playspaceChat.connect({participant:"page",token:"synthetic"}, "other-agent", {createClient:clientFactory});
    deferredStatus(); await tick(); await tick();
    assert.equal(connections.length,1);
    assert.deepEqual(connections[0],{kind:"token",to:"other-agent"});

    // Older restore cannot replace a NEW intent that arrived during cache load.
    holdLoad = true; deferredLoad = undefined;
    const older = context.playspaceChat.restore(); await tick();
    assert.ok(deferredLoad);
    await context.playspaceChat.connect({participant:"page",token:"synthetic"}, "newer-agent", {createClient:clientFactory});
    const before = restorations;
    deferredLoad(); holdLoad = false;
    assert.equal(await older,false);
    assert.equal(restorations,before);
    assert.equal(connections.at(-1).to,"newer-agent");
    assert.match(elements.get("connection").textContent,/LIVE.*authenticated/);

    for (const id of ["sample-mode", "live-mode"]) {
      holdLoad = true; deferredLoad = undefined;
      const stale = context.playspaceChat.restore(); await tick();
      assert.ok(deferredLoad);
      elements.get(id).click();
      deferredLoad(); holdLoad = false;
      assert.equal(await stale,false);
      assert.equal(restorations,before);
    }
    holdLoad = true;
    const stale = context.playspaceChat.restore(); await tick();
    const resolveOld = deferredLoad;
    const newest = context.playspaceChat.restore(); await tick();
    const resolveNew = deferredLoad;
    resolveNew(); assert.equal(await newest,true);
    const latestCount = restorations;
    resolveOld(); holdLoad = false;
    assert.equal(await stale,false);
    assert.equal(restorations,latestCount);
  } finally {
    context.playspaceChat.dispose();
    assert.equal(elements.get("connect-session").listeners.get("click").size,0);
    assert.equal(elements.get("restore").listeners.get("click").size,0);
  }
});
