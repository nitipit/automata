// Installed generic client + actual loopback WS; no browser DOM, model or Pi SDK.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
const [modulePath, endpoints] = process.argv.slice(2);
const {createMessageRouterClient} = await import(pathToFileURL(modulePath));
const credential = id => JSON.parse(readFileSync(join(endpoints,'participants',`${id}.json`)));
const peers = new Map(), messages = new Map();
const closures = [];
async function connect(id) {
  let client;
  client = createMessageRouterClient({onMessage:packet=>{
    messages.get(id).push(packet);
    if (packet.payload?.hold !== true && packet.expectReply)
      return client.respond(packet.id,{handledBy:id,echo:packet.payload});
  }});
  messages.set(id,[]);
  const ack = await client.connect(credential(id));
  assert.equal(ack.kind,'node');
  assert.equal(ack.network,credential(id).network);
  peers.set(id,client);
  return client;
}
async function roundTrip(source,target,payload) {
  let resolve;
  const reply = new Promise(done=>{resolve=done;});
  const sent = source.send(target,payload,{onResponse:resolve});
  assert.equal((await sent.accepted).status,'forwarded');
  const response = await reply;
  assert.equal(response.requestId,sent.id);
  assert.equal(response.from.kind,'node');
  assert.deepEqual(response.payload,{handledBy:target,echo:payload});
}
try {
  for (const fields of [{participant:'unknown'}, {token:'wrong'.repeat(8)}]) {
    const unauthorized = createMessageRouterClient();
    try { await assert.rejects(unauthorized.connect({...credential('desk'),...fields}),/router response|closed/i); }
    finally { unauthorized.close(); }
  }
  const desk = await connect('desk'), viewer = await connect('viewer');
  const worker = await connect('worker');
  await connect('blocked');
  const duplicate = createMessageRouterClient();
  try { await assert.rejects(duplicate.connect(credential('desk'))); }
  finally { duplicate.close(); }
  const status = await desk.status();
  assert.equal(status.network,'default');
  assert.deepEqual(status.destinations, [
    {id:'viewer',kind:'node',network:'default',connected:true},
    {id:'worker',kind:'node',network:'work',connected:true},
  ]);
  await roundTrip(desk,'viewer',{sameNetwork:[null,false]});
  await roundTrip(desk,'worker',{crossNetwork:'explicit'});
  await assert.rejects(desk.send('blocked',null).accepted,/forbidden/);
  await assert.rejects(viewer.send('worker',null).accepted,/forbidden/);
  await assert.rejects(worker.send('desk',null).accepted,/forbidden/);
  const held = desk.send('worker',{hold:true},{onResponse:packet=>closures.push(packet)});
  const accepted = await held.accepted;
  const message = messages.get('worker').at(-1);
  assert.equal(message.id,accepted.routeId);
  let closed;
  const notice = new Promise(resolve=>{closed=resolve;});
  const pending = desk.send('worker',{hold:true},{onResponse:closed});
  await pending.accepted;
  worker.close();
  assert.equal((await notice).type,'route_closed');
  const replacement = await connect('worker');
  assert.throws(()=>replacement.respond(message.id,{late:true}),/capability/);
  assert.equal(closures[0].uncertain,true);
  await roundTrip(desk,'worker',{fresh:true});
  const canceled = desk.send('viewer',{hold:true});
  await canceled.accepted;
  assert.equal((await desk.cancel(canceled.id)).status,'canceled');
  assert.equal((await desk.status()).pending,0);
  console.log('generic node credentials / network defaults / allow-block / discovery / replies / cleanup passed');
} finally { for (const client of peers.values()) client.close(); }
