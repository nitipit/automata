// Two real extension instances + native sockets, deterministic Pi API stubs, no LLM.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
const root = process.env.AGENT_BROWSER_BRIDGE_TEST_ROOT;
const endpoints = process.env.AGENT_ROUTER_ENDPOINTS;
const moduleRoot = process.env.AGENT_ROUTER_BROWSER;
const {default:register} = await import(pathToFileURL(join(root,'agent-router/index.ts')));
const {createAgentRouterChatClient} = await import(pathToFileURL(join(moduleRoot,'pi-client.js')));
const {createAgentRouterClient} = await import(pathToFileURL(join(moduleRoot,'client.js')));
const credential = id => JSON.parse(readFileSync(join(endpoints,'participants',id+'.json')));
async function until(predicate) {
  for (let i=0;i<200;i++) { if (await predicate()) return; await delay(10); }
  throw new Error('Expected condition did not become true');
}

function agent(identity) {
  const handlers = new Map(), tools = new Map(), users = [], custom = [], branch = [];
  let idle = true;
  const ctx = {cwd:root,ui:{setStatus(){}},isIdle:()=>idle,hasPendingMessages:()=>false,
    sessionManager:{getSessionId:()=>identity+'-session',getBranch:()=>branch}};
  register({on:(name,handler)=>handlers.set(name,handler),registerTool:tool=>tools.set(tool.name,tool),
    getActiveTools:()=>[],setActiveTools(){},
    sendUserMessage(content,options) {
      users.push({content,options});
      handlers.get('message_start')({message:{role:'user',content:[{type:'text',text:content}]}});
    },
    sendMessage(message,options) {
      custom.push({message,options});
      branch.push({type:'custom_message',...message});
    },
  });
  const tool = tools.get('agent_router');
  const call = params => tool.execute('test',params,undefined,undefined,ctx).then(value=>value.details);
  handlers.get('session_start')({},ctx);
  return {handlers,ctx,users,custom,call,setIdle:value=>{idle=value;}};
}

const first = agent('agent'), second = agent('peer');
const deliveriesA = [], deliveriesB = [], replies = [], states = [];
const a = createAgentRouterChatClient({to:'agent',onDelivery:p=>deliveriesA.push(p),onMessage:p=>replies.push(p),onState:p=>states.push(p)});
const b = createAgentRouterChatClient({to:'agent',onDelivery:p=>deliveriesB.push(p)});
try {
  await first.call({action:'open',endpoint:join(endpoints,'participants/agent.json')});
  await second.call({action:'open',endpoint:join(endpoints,'participants/peer.json')});
  await a.connect(credential('a')); await b.connect(credential('b'));
  const sent = a.sendMessage({text:'hello',__proto__:null});
  await until(()=>first.users.length===1);
  const text = first.users[0].content;
  assert.match(text,/source="page"\nparticipant="a"/);
  const inboundId = JSON.parse(text.split('\n').find(line=>line.startsWith('id=')).slice(3));
  await until(()=>states.some(state=>state.status==='admitted'));
  await first.call({action:'send',replyTo:inboundId,payload:{text:'answer'}});
  await until(()=>replies.length===1);
  assert.equal(replies[0].correlationId,sent.id);
  assert.deepEqual(replies[0].payload,{text:'answer'});

  // Same slot name belongs to separate authenticated sources; remote clear/inspect
  // cannot read or replace another page's retained nextTurn context.
  a.sendMessage({selection:'A'},{role:'context',deliverAs:'nextTurn',slot:'selection'});
  b.sendMessage({selection:'B'},{role:'context',deliverAs:'nextTurn',slot:'selection'});
  await until(()=>deliveriesA.some(p=>p.status==='buffered') && deliveriesB.some(p=>p.status==='buffered'));
  assert.equal((await first.call({action:'inspect_context'})).entries.length,2);
  a.inspectContext();
  await until(()=>deliveriesA.some(p=>p.status==='inspected'));
  assert.equal(deliveriesA.find(p=>p.status==='inspected').details.entries.length,1);
  a.clearContext('selection');
  await until(()=>deliveriesA.filter(p=>p.status==='cleared').length===2);
  assert.equal((await first.call({action:'inspect_context'})).entries.length,1);
  assert.equal(deliveriesB.some(p=>p.status==='cleared'),false);
  const snapshot = first.handlers.get('before_agent_start')();
  assert.match(snapshot.message.content,/"selection":"B"/);
  first.handlers.get('message_start')({message:{role:'custom',...snapshot.message}});
  await until(()=>deliveriesB.some(p=>p.status==='attached'));
  assert.equal((await first.call({action:'inspect_context'})).entries.length,0);

  // Native immediate context receipt still confirms from canonical branch records.
  a.sendMessage({note:'canonical'},{role:'context',deliverAs:'immediate'});
  await until(()=>deliveriesA.some(p=>p.status==='attached'));
  assert.equal(first.custom.length,1);
  assert.equal(first.custom[0].options.triggerTurn,undefined);

  // Agent→agent is explicit, with peer provenance and asynchronously consumed reply.
  const outbound = await first.call({action:'route',to:'peer',payload:{question:'peer'}});
  await until(()=>second.users.length===1);
  assert.match(second.users[0].content,/source="agent"\nparticipant="agent"\nsessionId="agent-session"/);
  const peerId = JSON.parse(second.users[0].content.split('\n').find(line=>line.startsWith('id=')).slice(3));
  await second.call({action:'send',replyTo:peerId,payload:{answer:'peer'}});
  await until(async()=> (await first.call({action:'status'})).outgoing.some(p=>p.id===outbound.id && p.final));
  assert.equal(first.users.length,1); // response did not start another model turn
  assert.deepEqual((await first.call({action:'receive',replyTo:outbound.id})).payload,{answer:'peer'});
  await assert.rejects(first.call({action:'receive',replyTo:outbound.id}),/No matching/);
  await assert.rejects(second.call({action:'route',to:'b',payload:null}),/forbidden/);

  first.setIdle(false);
  a.sendMessage({text:'busy'});
  await until(()=>states.some(p=>p.status==='rejected'));
  assert.equal(first.users.length,1);
  first.setIdle(true);

  // A sender closing does not prevent the Pi owner from settling its lost reply.
  a.sendMessage({text:'disconnect'});
  await until(()=>first.users.length===2);
  const lostId = JSON.parse(first.users[1].content.split('\n').find(line=>line.startsWith('id=')).slice(3));
  a.close(); await delay(40);
  assert.equal((await first.call({action:'send',replyTo:lostId,payload:null})).status,'delivery_uncertain');
  await a.connect(credential('a'));
  a.sendMessage({text:'after reconnect'});
  await until(()=>first.users.length===3);
  const freshId = JSON.parse(first.users[2].content.split('\n').find(line=>line.startsWith('id=')).slice(3));
  await first.call({action:'send',replyTo:freshId,payload:null});

  // Tree navigation invalidates the binding and buffers rather than leaking across branches.
  first.handlers.get('session_tree')();
  await assert.rejects(first.call({action:'status'}),/Open/);
  console.log('two Pi adapter instances / Chat / context isolation / agent routing passed');
} finally {
  a.close(); b.close();
  first.handlers.get('session_shutdown')(); second.handlers.get('session_shutdown')();
}
