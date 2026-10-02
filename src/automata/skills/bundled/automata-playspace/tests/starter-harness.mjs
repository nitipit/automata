import fs from "node:fs/promises";
import path from "node:path";
import vm from "node:vm";

/** Executes actual staged starter modules; DOM, cache and remote boundaries are fakes. */
export async function starterHarness({requestStorage = new Map(), authenticated = true} = {}) {
  class Element {
    value = ""; textContent = ""; disabled = false; hidden = false; open = false;
    elements = []; listeners = new Map(); dataset = {}; attributes = new Map();
    addEventListener(name, fn) { if (!this.listeners.has(name)) this.listeners.set(name, new Set()); this.listeners.get(name).add(fn); }
    removeEventListener(name, fn) { this.listeners.get(name)?.delete(fn); }
    fire(name, detail = {}) {
      const event = {target:this,preventDefault(){this.defaultPrevented=true;}, ...detail};
      for (const fn of this.listeners.get(name) ?? []) fn(event);
      return event;
    }
    click() { this.fire("click"); }
    focus() { document.activeElement = this; }
    setAttribute(name, value) { this.attributes.set(name, value); }
    showModal() { this.open = true; }
    close() {
      if (!this.open) return;
      this.fire("beforetoggle", {oldState:"open",newState:"closed"});
      this.open = false;
    } // tests dispatch the separately queued native close notification
    querySelector() { return summary; }
    contains(element) { return element === this || this.elements.includes(element); }
    closest() { return null; }
  }
  const ids = ["pairing-state", "pairing-code", "target-participant", "pairing-form", "pair-browser", "connect-session",
    "forget-pairing", "target-preference-state", "connection", "recovery", "sample-mode", "live-mode",
    "sample-form", "save", "restore", "startup-error", "connection-dialog", "connection-settings", "tools-menu",
    "close-connection", "cancel-connection", "selected-target", "connection-detail", "page-participant",
    "request-pairing-controls", "request-pairing", "check-pairing-request", "cancel-pairing-request",
    "pairing-request-locator", "pairing-request-state", "check-session-status", "copy-pairing-message",
    "pairing-message", "pairing-message-box", "copy-pairing-state", "request-expiry", "request-dismiss-note",
    "dialog-target", "choose-agent", "done-connection", "connection-advanced", "advanced-check-session", "forget-row"];
  const elements = new Map(ids.map(id => [id, new Element()]));
  const get = id => elements.get(id), summary = new Element();
  get("target-participant").value = "pc1-agent";
  get("pairing-form").elements = [get("pairing-code"), get("pair-browser")];
  get("request-pairing-controls").elements = [get("request-pairing"), get("check-pairing-request"), get("cancel-pairing-request"), get("copy-pairing-message"), get("pairing-message")];
  const controls = {candidate:null, holdStatus:false, holdPair:false, holdLoad:false, holdConnect:false,
    authenticated, participant:"page", restorations:0, messages:[], connections:[], clients:[], requests:[],
    requestRecords:new Map(), clipboard:[]};
  const chat = Object.assign(new Element(), {interrupt(){},setConnection(){},setAgentBusy(){},setStatus(){},
    snapshot:()=>({}),restore:()=>{controls.restorations++;return true;},addMessage:(...args)=>controls.messages.push(args),
    dispose(){},reject(){},receiveMessage(){},markSent(){}});
  const storage = new Map();
  const document = {querySelector:selector => selector === "ps-chat" ? chat : get(selector.slice(1)), getElementById:get};
  const context = vm.createContext({URL, setTimeout, clearTimeout, queueMicrotask, AbortController,
    crypto:globalThis.crypto,
    navigator:{clipboard:{writeText:async text => {
      if (controls.clipboardFail) throw new Error("Clipboard blocked");
      controls.clipboard.push(text);
    }}},

    sessionStorage:{getItem:key => requestStorage.get(key) ?? null,
      setItem:(key,value) => requestStorage.set(key,value),removeItem:key => requestStorage.delete(key)},
    location:{origin:"http://127.0.0.1:8775",href:"http://127.0.0.1:8775/"}, document,
    addEventListener(){},removeEventListener(){},
    localStorage:{getItem:key => storage.get(key) ?? null,setItem:(key,value) => storage.set(key,value)},
    fetch:async (url, options) => {
      const endpoint = new URL(url).pathname;
      const requestKinds = {"/session/request":"RequestCreate", "/session/request-status":"RequestStatus",
        "/session/request-cancel":"RequestCancel", "/session/request-redeem":"RequestRedeem"};
      const kind = requestKinds[endpoint] ?? (url.endsWith("/pair") ? "Pair" : url.endsWith("/logout") ? "Forget" : "Status");
      controls.requests.push({url,options});
      const response = () => {
        if (controls.failNext === kind) { controls.failNext = null; return {ok:false,status:503}; }
        if (kind === "Forget") controls.authenticated = false;
        let result = {authenticated:controls.authenticated,participant:controls.participant,expiresAt:100};
        if (requestKinds[endpoint]) {
          const packet = JSON.parse(options.body);
          let record = [...controls.requestRecords.values()].find(value => value.capability === packet.capability);
          if (kind === "RequestCreate" && !record) {
            const request = "RP-" + String(controls.requestRecords.size + 1).padStart(10,"0");
            record = {...packet, request, state:"pending", expiresAt:Date.now()/1000+300};
            controls.requestRecords.set(request,record);
          }
          if (!record || (kind !== "RequestCreate" && record.request !== packet.request)) return {ok:false,status:400};
          if (kind === "RequestCancel") record.state = "cancelled";
          if (kind === "RequestRedeem") {
            if (controls.authenticated || record.state !== "approved") return {ok:false,status:400};
            record.state = "redeemed"; controls.authenticated = true;
            controls.participant = record.participant;
            result = {authenticated:true,participant:record.participant,expiresAt:Date.now()/1000+3600};
          } else {
            const {capability, ...safe} = record; result = safe;
          }
        }
        return {ok:true,json:async()=>result};
      };
      if (!controls[`hold${kind}`]) return response();
      controls[`hold${kind}`] = false;
      return new Promise(resolve => { controls[`resolve${kind}`] = () => resolve(response()); });
    },
  });
  const clientFactory = options => {
    const client = {closed:false,
      async connectSession() {
        controls.connections.push({kind:"session",to:options.to});
        if (controls.holdConnect) {
          controls.holdConnect = false;
          await new Promise(resolve => {controls.resolveConnect = resolve;});
        }
        options.onState({status:"connected"});
      },
      async connect() { controls.connections.push({kind:"token",to:options.to}); options.onState({status:"connected"}); },
      async status() { return {destinations:[{id:options.to,kind:"agent",connected:true}]}; },
      close(){this.closed=true;},isConnected(){return !this.closed;}, sendMessage(){controls.sends=(controls.sends??0)+1;},
    };
    controls.clients.push(client);
    return client;
  };
  const fakes = {
    "lib/playspace.js":{registerPlayspace(){},ContractError:class extends Error{},text:value=>value,formContracts:{}},
    "lib/recovery.js":{createCacheRecovery:()=>({flush:async()=>{},load:async()=>{
      if (!controls.holdLoad) return controls.candidate;
      return new Promise(resolve => {controls.resolveLoad=()=>resolve(controls.candidate);});
    },save:async()=>true,dispose(){}})},
    "lib/state.js":{validateStarterSnapshot:value=>value},
    "sample.js":{sampleForm:()=>"sample-form",sampleReply:()=>null},
    "router/pi-client.js":{createMessageRouterChatClient:clientFactory},
  };
  const modules = new Map(), stage = path.dirname(process.env.PLAYSPACE_LIB);
  async function load(name) {
    if (modules.has(name)) return modules.get(name);
    const exports = fakes[name];
    const module = exports ? new vm.SyntheticModule(Object.keys(exports), function() {
      for (const [key,value] of Object.entries(exports)) this.setExport(key,value);
    }, {context,identifier:name}) : new vm.SourceTextModule(await fs.readFile(path.join(stage,name),"utf8"), {
      context,identifier:name,
      async importModuleDynamically(specifier, parent) {
        if (controls.holdImport) await new Promise(resolve => {controls.resolveImport=resolve;});
        const imported = await load(path.posix.normalize(path.posix.join(path.posix.dirname(parent.identifier),specifier)));
        if (imported.status !== "evaluated") await imported.evaluate();
        return imported;
      },
    });
    modules.set(name,module);
    await module.link((specifier,parent) => load(path.posix.normalize(path.posix.join(path.posix.dirname(parent.identifier),specifier))));
    return module;
  }
  await (await load("index.js")).evaluate();
  const tick = () => new Promise(resolve => setImmediate(resolve));
  await tick();
  return {get,controls,context,clientFactory,chat,document,storage,requestStorage,tick,summary};
}
