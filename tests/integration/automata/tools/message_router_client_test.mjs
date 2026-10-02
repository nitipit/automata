import assert from 'node:assert/strict';
import test from 'node:test';
import {createMessageRouterClient, createAgentRouterClient} from '../../../../src/automata/tools/message-router/browser/client.js';
import {createMessageRouterChatClient, createAgentRouterChatClient} from '../../../../src/automata/tools/message-router/browser/pi-client.js';
import {createBrowserSessionAuth} from '../../../../src/automata/tools/message-router/browser/session.js';
import {createPairingRequest} from '../../../../src/automata/tools/message-router/browser/pairing-request.js';

test('old browser exports are aliases of the canonical message-router factories', () => {
  assert.equal(createAgentRouterClient, createMessageRouterClient);
  assert.equal(createAgentRouterChatClient, createMessageRouterChatClient);
});

class Socket {
  static all = [];
  readyState = 0; sent = []; listeners = new Map();
  constructor() { Socket.all.push(this); queueMicrotask(() => { this.readyState = 1; this.listeners.get('open')?.(); }); }
  addEventListener(event, callback) { this.listeners.set(event, callback); }
  send(raw) {
    const packet = JSON.parse(raw); this.sent.push(packet);
    if (packet.type === 'hello') this.message({v:2,type:'hello_ack',participant:packet.participant,kind:'page'});
    else this.handle?.(packet);
  }
  message(value) { this.onmessage?.({data:JSON.stringify(value)}); }
  close() { this.readyState = 3; this.onclose?.(); }
}
const credentials = {wsUrl:'ws://127.0.0.1:8787/ws', participant:'page',token:'p'.repeat(32)};

function acknowledge(socket, packet, fields = {}) {
  socket.message({v:2,type:'result',requestId:packet.requestId,status:'forwarded',...fields});
}

test('response before route acknowledgment, final claim, and no replay across reconnect', async () => {
  const responses = [], messages = [];
  const client = createMessageRouterClient({WebSocketImpl:Socket,onResponse:p=>responses.push(p),onMessage:p=>messages.push(p)});
  await client.connect(credentials);
  const socket = Socket.all.at(-1);
  socket.handle = packet => {
    if (packet.type === 'route') {
      socket.message({v:2,type:'response',requestId:packet.requestId,id:'route-one',from:{id:'peer',kind:'page'},payload:null,metadata:{},final:true});
      acknowledge(socket,packet,{routeId:'route-one'});
    } else acknowledge(socket,packet);
  };
  assert.equal((await client.send('peer', {constructor:[false]}).accepted).status,'forwarded');
  assert.equal(responses.length,1);
  assert.equal(responses[0].payload,null);
  socket.message({v:2,type:'message',id:'inbound',from:{id:'peer',kind:'page'},to:'page',payload:0,metadata:{},expectReply:true});
  assert.equal(messages.length,1);
  assert.throws(()=>client.respond('inbound',undefined), /non-JSON/);
  await client.respond('inbound', false);
  assert.throws(()=>client.respond('inbound', false), /capability/);
  const old = socket;
  await client.connect(credentials);
  const fresh = Socket.all.at(-1);
  old.onclose();
  old.message({v:2,type:'message',id:'late',from:{id:'peer',kind:'page'},to:'page',payload:0,metadata:{},expectReply:true});
  assert.equal(client.isConnected(),true);
  assert.equal(messages.length,1);
  assert.equal(fresh.sent.length,1); // hello only, no replay
  client.close();
  assert.throws(()=>client.send('peer',null), /disconnected/);
});

test('uncertain transport and forged sender/correlation close without resending', async () => {
  const responses = [];
  const client = createMessageRouterClient({WebSocketImpl:Socket,onResponse:p=>responses.push(p)});
  await client.connect(credentials);
  const socket = Socket.all.at(-1);
  socket.handle = packet => acknowledge(socket, packet, {routeId:'pending'});
  const sent = client.send('expected',null);
  await sent.accepted;
  socket.message({v:2,type:'response',requestId:sent.id,id:'pending',from:{id:'wrong',kind:'agent'},payload:'bad',metadata:{},final:true});
  assert.equal(client.isConnected(),false);
  assert.equal(responses.length,1);
  assert.equal(responses[0].uncertain,true);
  assert.equal(socket.sent.length,2);
});

test('intermediate application receipts and cancellation release bounded correlation', async () => {
  const responses = [];
  const client = createMessageRouterClient({WebSocketImpl:Socket,onResponse:p=>responses.push(p)});
  await client.connect(credentials);
  const socket = Socket.all.at(-1);
  socket.handle = packet => acknowledge(socket, packet, {routeId:packet.requestId});
  const sent = client.send('agent',null);
  await sent.accepted;
  socket.message({v:2,type:'response',requestId:sent.id,id:sent.id,from:{id:'agent',kind:'agent'},payload:null,metadata:{pi:{status:'buffered'}},final:false});
  assert.equal(responses.length,1);
  await client.cancel(sent.id);
  assert.equal(socket.sent.at(-1).type,'cancel');
  socket.message({v:2,type:'response',requestId:sent.id,id:sent.id,from:{id:'agent',kind:'agent'},payload:'late',metadata:{},final:true});
  assert.equal(responses.length,1);
  assert.throws(()=>client.send('agent', NaN), /finite/);
  client.close();
});

class SessionSocket extends Socket {
  send(raw) {
    const packet = JSON.parse(raw);
    this.sent.push(packet);
    if (packet.type === 'hello') this.message({v:2,type:'hello_ack',participant:'paired-page',kind:'page'});
    else this.handle?.(packet);
  }
}
test('cookie session uses shared correlation without token hello, cross-origin fallback or replay', async () => {
  const previous = globalThis.location;
  globalThis.location = {origin:'http://127.0.0.1:8787'};
  const client = createMessageRouterClient({WebSocketImpl:SessionSocket});
  const session = {wsUrl:'ws://127.0.0.1:8787/session/ws',participant:'paired-page'};
  try {
    for (const wsUrl of ['ws://127.0.0.1:8788/session/ws', 'ws://localhost:8787/session/ws',
                         'ws://127.0.0.1:8787/ws', 'ws://127.0.0.1:8787/session/ws?participant=other'])
      assert.throws(() => client.connectSession({...session, wsUrl}), /origin|URL/);
    await client.connectSession(session);
    const socket = Socket.all.at(-1);
    assert.deepEqual(socket.sent, [{v:2,type:'hello'}]);
    socket.handle = packet => acknowledge(socket, packet, {routeId:'cookie-route'});
    const sent = client.send('agent', {nested:[null,false,{arbitrary:'kept'}]});
    assert.equal((await sent.accepted).status, 'forwarded');
    assert.deepEqual(socket.sent.at(-1).payload, {nested:[null,false,{arbitrary:'kept'}]});
    client.close();
    await client.connectSession(session);
    assert.deepEqual(Socket.all.at(-1).sent, [{v:2,type:'hello'}]);
    assert.throws(() => client.respond('cookie-route', null), /capability/);
  } finally { client.close(); globalThis.location = previous; }
});

test('session helper keeps credentials same-origin, status inert and pairing code out of connection data', async () => {
  const calls = [];
  const auth = createBrowserSessionAuth({location:{origin:'http://127.0.0.1:8787'},
    fetchImpl:async (url, options) => {
      calls.push({url,options});
      return {ok:true,json:async()=>({authenticated:!url.endsWith('/logout'),participant:'page',expiresAt:1})};
    }});
  assert.equal((await auth.status()).authenticated, true);
  assert.equal(calls[0].options.method,'GET');
  const paired = await auth.pair('private-synthetic-code');
  assert.deepEqual(auth.connection(paired), {wsUrl:'ws://127.0.0.1:8787/session/ws',participant:'page'});
  assert.deepEqual(JSON.parse(calls[1].options.body), {code:'private-synthetic-code'});
  await auth.forget();
  for (const call of calls) {
    assert.equal(call.options.mode,'same-origin');
    assert.equal(call.options.credentials,'same-origin');
    assert.equal(call.options.cache,'no-store');
  }
  assert.throws(() => createBrowserSessionAuth({location:{origin:'http://localhost:8787'}}), /origin/);
});

test('transient requester survives refresh and lost create response without exposing capability or replay', async () => {
  const values = new Map(), calls = [];
  const storage = {getItem:key => values.get(key) ?? null, setItem:(key,value) => values.set(key,value),
    removeItem:key => values.delete(key)};
  let clock = 1000, loseResponse = true, state = 'pending';
  const auth = {
    async requestPairing(capability) {
      calls.push({action:'create',capability});
      assert.ok([...values.values()][0].includes(capability)); // saved BEFORE transmission
      if (loseResponse) { loseResponse=false; throw new Error('response lost'); }
      return {request:'RP-123456789A',state,expiresAt:1300};
    },
    async requestStatus(request, capability) {
      calls.push({action:'status',request,capability});
      return {request,state,expiresAt:1300,participant:'page'};
    },
    async redeemRequest(request, capability) {
      calls.push({action:'claim',request,capability}); state='redeemed';
      return {authenticated:true,participant:'page',expiresAt:2000};
    },
  };
  const options = {auth,location:{href:'http://127.0.0.1:8787/playspace/'},getStorage:()=>storage,now:()=>clock*1000};
  const first=createPairingRequest(options);
  await assert.rejects(first.start(), /lost/);
  const second=createPairingRequest(options);
  assert.equal(second.restore().state,'pending');
  assert.equal(calls.length,1); // restore never creates/checks/claims/connects
  const view=await second.start();
  assert.equal(calls[0].capability,calls[1].capability);
  assert.match(calls[0].capability,/^[0-9a-f]{64}$/);
  assert.ok(!JSON.stringify(view).includes(calls[0].capability));
  state='approved';
  assert.equal((await second.check()).state,'approved');
  assert.equal(calls.filter(value=>value.action==='claim').length,0);
  assert.equal((await second.claim()).authenticated,true);
  assert.equal(second.view().state,'redeemed');
  await assert.rejects(second.claim(),/not approved/);
  clock=1300;
  await assert.rejects(second.check(),/expired/);
  assert.equal(second.view().state,'redeemed'); // request TTL cannot retire a claimed session
  await assert.rejects(second.start(),/explicit session revocation/);
  assert.throws(() => second.clearExpired(),/explicit session revocation/);
  second.clearExpired({revokedParticipant:'page'}); // caller observed matching explicit logout
  assert.equal(values.size,0);
});

test('requester storage denial stops creation; stale responses cannot overwrite a newer binding', async () => {
  let calls=0, stored=null, resolveOld;
  const auth={requestPairing:async()=>{calls++;return new Promise(resolve=>{resolveOld=resolve;});}};
  const base={auth,location:{href:'http://127.0.0.1:8787/'}};
  const denied=createPairingRequest({...base,getStorage:()=>{throw new Error('blocked');}});
  await assert.rejects(denied.start(),/blocked/);
  assert.equal(calls,0);
  const storage={getItem:()=>stored,setItem:(_,value)=>{stored=value;},removeItem:()=>{stored=null;}};
  const active=createPairingRequest({...base,getStorage:()=>storage});
  const pending=active.start();
  const original=JSON.parse(stored);
  const newer={...original,capability:'f'.repeat(64),request:'RP-FFFFFFFFFF'};
  stored=JSON.stringify(newer); // another same-profile local intent owns storage now
  resolveOld({request:'RP-AAAAAAAAAA',state:'pending',expiresAt:original.expiresAt});
  await pending;
  assert.deepEqual(JSON.parse(stored),newer);
});

test('request HTTP wrappers are same-origin, bounded, strict and never carry locator credentials in URLs', async () => {
  const calls=[];
  const auth=createBrowserSessionAuth({location:{origin:'http://127.0.0.1:8787'},fetchImpl:async(url,options)=>{
    calls.push({url,options});
    return {ok:true,json:async()=>url.endsWith('/request-redeem') ?
      {authenticated:true,participant:'page',expiresAt:2000} :
      {request:'RP-123456789A',state:'pending',expiresAt:1300}};
  }});
  await auth.requestPairing('a'.repeat(64));
  await auth.requestStatus('RP-123456789A','a'.repeat(64));
  await auth.cancelRequest('RP-123456789A','a'.repeat(64));
  await auth.redeemRequest('RP-123456789A','a'.repeat(64));
  for (const {url,options} of calls) {
    assert.equal(new URL(url).search,'');
    assert.equal(options.method,'POST');
    assert.equal(options.credentials,'same-origin');
    assert.equal(options.mode,'same-origin');
    assert.equal(options.cache,'no-store');
    assert.ok(options.signal instanceof AbortSignal);
    assert.equal(JSON.parse(options.body).capability,'a'.repeat(64));
  }
  const bad=createBrowserSessionAuth({location:{origin:'http://127.0.0.1:8787'},
    fetchImpl:async()=>({ok:true,json:async()=>({authenticated:true})})});
  await assert.rejects(bad.requestPairing('a'.repeat(64)),/Invalid pairing request/);
});

test('request HTTP timeout aborts once without retry or claiming rollback', async () => {
  let calls=0;
  const auth=createBrowserSessionAuth({location:{origin:'http://127.0.0.1:8787'},
    fetchImpl:(_,options)=>new Promise((resolve,reject)=>{
      calls++;
      options.signal.addEventListener('abort',()=>reject(new Error('aborted')),{once:true});
    })});
  await assert.rejects(auth.requestPairing('a'.repeat(64)),/aborted/);
  assert.equal(calls,1);
});

test('explicit create after restart replaces only pending locator and does not slide local deadline', async () => {
  let stored=null, clock=1000, locator='RP-AAAAAAAAAA', state='pending', calls=0;
  const storage={getItem:()=>stored,setItem:(_,value)=>{stored=value;}};
  const request=createPairingRequest({location:{href:'http://127.0.0.1:8787/'},
    getStorage:()=>storage,now:()=>clock*1000,auth:{async requestPairing() {
      calls++; return {request:locator,state,expiresAt:clock+300};
    }}});
  assert.equal((await request.start()).expiresAt,1300);
  clock=1100; locator='RP-BBBBBBBBBB';
  assert.equal(request.view().request,'RP-AAAAAAAAAA'); // no implicit retry
  assert.equal(calls,1);
  const fresh=await request.start();
  assert.equal(fresh.request,locator);
  assert.equal(fresh.state,'pending');
  assert.equal(fresh.expiresAt,1300);
  locator='RP-CCCCCCCCCC'; state='approved';
  await assert.rejects(request.start(),/Request changed/); // never inherits another approval
  assert.equal(request.view().request,'RP-BBBBBBBBBB');
});
