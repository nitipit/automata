// Real native WebSocket clients against the installed Python server; no model calls.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
const [modulePath, endpoints] = process.argv.slice(2);
const {createAgentRouterClient} = await import(pathToFileURL(modulePath));
const clients = [];
try {
  for (const identity of ['a','b','agent']) {
    const credential = JSON.parse(readFileSync(join(endpoints,'participants',`${identity}.json`)));
    let client;
    client = createAgentRouterClient({onMessage: async packet => {
      await client.respond(packet.id,{handledBy:identity,echo:packet.payload});
    }});
    clients.push(client);
    await client.connect({...credential,...(identity === 'agent' ? {sessionId:'native-stub'} : {})});
  }
  for (const [source, target] of [[0,'b'],[0,'agent'],[2,'a']]) {
    let resolve;
    const reply = new Promise(done => {resolve = done;});
    const sent = clients[source].send(target,{value:null},{onResponse:resolve});
    assert.equal((await sent.accepted).status,'forwarded');
    assert.deepEqual((await reply).payload,{handledBy:target,echo:{value:null}});
  }
  assert.equal((await clients[0].status()).participant,'a');
  console.log('native JS page-page/page-agent/agent-page routes passed');
} finally { for (const client of clients) client.close(); }
