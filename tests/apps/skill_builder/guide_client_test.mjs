/** Exercise guide API calls against the shipped client, without a socket/server. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {createMessageRouterClient} from '../../../src/automata/tools/message-router/browser/client.js';

class FixtureSocket {
  static instance;
  readyState = 1;
  frames = [];
  constructor() { FixtureSocket.instance = this; }
  addEventListener(event, handler) { if (event === 'open') queueMicrotask(handler); }
  send(text) {
    const frame = JSON.parse(text); this.frames.push(frame);
    if (frame.type === 'hello') queueMicrotask(() => this.deliver({v:2,type:'hello_ack',participant:frame.participant,kind:frame.participant === 'desk' ? 'page' : 'agent'}));
  }
  deliver(packet) { this.onmessage({data:JSON.stringify(packet)}); }
  close() { this.readyState = 3; }
  result(fields = {}) {
    const requestId = this.frames.at(-1).requestId;
    this.deliver({v:2,type:'result',requestId,...fields});
  }
}
async function connected(participant, handlers = {}) {
  const client = createMessageRouterClient({WebSocketImpl:FixtureSocket,...handlers});
  await client.connect({wsUrl:'ws://127.0.0.1:8787/ws',participant,token:'fixture-not-a-real-credential',...(participant === 'desk' ? {} : {sessionId:'worker-example'})});
  return [client, FixtureSocket.instance];
}

test('guide status shape and independent request/reply correlation use actual API', async () => {
  const responses = [];
  const [desk,socket] = await connected('desk', {onResponse:value => responses.push(value)});
  try {
    const status = desk.status();
    socket.result({status:'connected',participant:'desk',destinations:[{id:'viewer',kind:'page',connected:true},{id:'worker',kind:'agent',connected:true}],pending:0});
    assert.equal((await status).pending,0);
    const request = desk.send('worker',{question:'Check this outline?'});
    assert.equal(socket.frames.at(-1).expectReply,true);
    assert.equal(socket.frames.at(-1).requestId,request.id);
    // Shipped client accepts a terminal response BEFORE the forwarding result.
    socket.deliver({v:2,type:'response',id:'route-1',requestId:request.id,from:{id:'worker',kind:'agent',sessionId:'worker-example'},payload:{answer:'Outline checked'},metadata:{},final:true});
    socket.result({status:'forwarded',routeId:'route-1'});
    assert.equal((await request.accepted).routeId,'route-1');
    assert.equal(responses[0].requestId,request.id);
    assert.notEqual(responses[0].id,request.id);
  } finally { desk.close(); }
});
test('one-way uses false; forbidden/offline reject, uncertain resolves', async () => {
  const [desk,socket] = await connected('desk');
  try {
    const notification = desk.send('viewer',{notice:'Outline changed'},{expectReply:false});
    assert.equal(socket.frames.at(-1).expectReply,false);
    socket.result({status:'forwarded',routeId:'notice-1'});
    assert.equal((await notification.accepted).status,'forwarded');
    for (const error of ['forbidden','offline']) {
      const request = desk.send('worker',null);
      socket.result({status:'rejected',error});
      await assert.rejects(request.accepted,new RegExp(error));
    }
    const uncertain = desk.send('worker',null);
    socket.result({status:'uncertain',routeId:'uncertain-1'});
    assert.equal((await uncertain.accepted).status,'uncertain');
  } finally { desk.close(); }
});
test('recipient responds with message.id and final defaults true', async () => {
  let response;
  const [worker,socket] = await connected('worker', {onMessage:message => {
    if (message.expectReply) response = worker.respond(message.id,{answer:'Outline checked'});
  }});
  try {
    socket.deliver({v:2,type:'message',id:'inbound-route',from:{id:'desk',kind:'page'},to:'worker',payload:null,metadata:{},expectReply:true});
    assert.equal(socket.frames.at(-1).routeId,'inbound-route');
    assert.equal(socket.frames.at(-1).final,true);
    socket.result({status:'forwarded'});
    await response;
  } finally { worker.close(); }
});
test('cancel takes sender request.id, sends routeId and has separate RPC ID', async () => {
  const [desk,socket] = await connected('desk');
  try {
    const request = desk.send('worker',null);
    socket.result({status:'forwarded',routeId:'pending-route'});
    await request.accepted;
    const canceled = desk.cancel(request.id);
    assert.equal(socket.frames.at(-1).routeId,'pending-route');
    assert.notEqual(socket.frames.at(-1).requestId,request.id);
    socket.result({status:'canceled'});
    assert.equal((await canceled).status,'canceled');
  } finally { desk.close(); }
});
