import assert from 'node:assert/strict';
import test from 'node:test';
import {createMessageRouterClient, createAgentRouterClient} from '../../../../src/automata/tools/message-router/browser/client.js';
import {createMessageRouterChatClient, createAgentRouterChatClient} from '../../../../src/automata/tools/message-router/browser/pi-client.js';

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
