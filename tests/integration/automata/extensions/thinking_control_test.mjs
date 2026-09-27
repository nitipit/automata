// Real installed Pi SDK + local provider stub. No paid calls or remote transport.
import assert from 'node:assert/strict';
import test from 'node:test';
import {join} from 'node:path';
const root = process.env.THINKING_TEST_ROOT;
const pkg = process.env.AGENT_BROWSER_BRIDGE_NATIVE_PI_PACKAGE;
const sdk = await import(join(pkg, 'dist/index.js'));
const ai = await import(join(pkg, '../pi-ai/dist/index.js'));
const {operation, apply} = await import(join(root, 'thinking-control/local.ts'));
const model = {id:'thinking-fixture',name:'thinking fixture',api:'openai-responses',provider:'fixture',
  baseUrl:'http://unused.invalid',reasoning:true,input:['text'],contextWindow:32000,maxTokens:1000,
  cost:{input:0,output:0,cacheRead:0,cacheWrite:0},thinkingLevelMap:{xhigh:null,max:'max'}};

test('local operation validation and native supported-level metadata',()=>{
  assert.deepEqual(ai.getSupportedThinkingLevels({...model,reasoning:false}),['off']);
  assert.deepEqual(ai.getSupportedThinkingLevels({...model,thinkingLevelMap:undefined}),['off','minimal','low','medium','high']);
  assert.deepEqual(ai.getSupportedThinkingLevels({...model,thinkingLevelMap:{minimal:null,xhigh:'xhigh'}}),['off','low','medium','high','xhigh']);
  assert.deepEqual(operation({action:'inspect'}),{action:'inspect'});
  assert.deepEqual(operation({action:'set',level:'high'}),{action:'set',level:'high'});
  for (const input of [null,[],{action:'set',level:'ultra'},{action:'set'},
    {action:'inspect',level:'high'},{action:'inspect',payload:{}},{action:'load_grant'}])
    assert.throws(()=>operation(input));
  assert.throws(()=>apply({}, {model:undefined}, {action:'inspect'}),/No active model/);
  let writes=0;
  const pi={getThinkingLevel:()=> 'off',setThinkingLevel:()=>{writes++;}};
  const ctx={model:{...model,reasoning:false},isIdle:()=>true,sessionManager:{getSessionId:()=> 'local'}};
  assert.throws(()=>apply(pi,ctx,{action:'set',level:'high'}),/Unsupported/);
  assert.equal(writes,0);
  assert.equal(apply(pi,ctx,{action:'inspect'}).effective,'off');
});

test('native local effort changes affect next requests, not in-flight reasoning or global defaults',async()=>{
  let onStream, streamError;
  const calls=[];
  const settings=sdk.SettingsManager.inMemory({defaultThinkingLevel:'low',compaction:{enabled:false},retry:{enabled:false}});
  const loader=new sdk.DefaultResourceLoader({cwd:root,agentDir:join(root,'agent'),settingsManager:settings,
    additionalExtensionPaths:[join(root,'thinking-control')],
    noSkills:true,noPromptTemplates:true,noThemes:true,agentsFilesOverride:()=>({agentsFiles:[]}),systemPromptOverride:()=> 'Offline fixture.',
    extensionFactories:[pi=>pi.registerProvider('fixture',{api:model.api,apiKey:'fixture',baseUrl:model.baseUrl,models:[model],
      streamSimple:(_model,_context,options)=>{
        calls.push({reasoning:options.reasoning,signal:options.signal});
        const stream=ai.createAssistantMessageEventStream();
        const n=calls.length;
        const message={role:'assistant',content:n<3 ? [{type:'toolCall',id:`call-${n}`,name:'thinking_control',arguments:n===1?{action:'inspect'}:{action:'set',level:'medium'}}] : [{type:'text',text:'done'}],
          api:model.api,provider:model.provider,model:model.id,stopReason:n<3?'toolUse':'stop',timestamp:Date.now(),
          usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}};
        queueMicrotask(async()=>{try{await onStream?.(n,options);}catch(error){streamError=error;} stream.push({type:'done',reason:message.stopReason,message});stream.end(message);});
        return stream;
      }})]});
  await loader.reload(); assert.deepEqual(loader.getExtensions().errors,[]);
  const runtime=await sdk.ModelRuntime.create({authPath:join(root,'auth.json'),modelsPath:join(root,'models.json'),modelsStorePath:join(root,'models-store.json'),allowModelNetwork:false});
  const manager=sdk.SessionManager.inMemory(root);
  const {session}=await sdk.createAgentSession({cwd:root,agentDir:join(root,'agent'),resourceLoader:loader,modelRuntime:runtime,model,thinkingLevel:'low',settingsManager:settings,sessionManager:manager,tools:['thinking_control']});
  try {
    const extensionErrors=[];
    await session.bindExtensions({onError:error=>extensionErrors.push(error)});
    const think=args=>session.agent.state.tools.find(t=>t.name==='thinking_control').execute('test',args).then(v=>v.details);
    const initial=await think({action:'inspect'});
    assert.equal(initial.sessionId,manager.getSessionId());
    assert.deepEqual(initial.model,{provider:model.provider,id:model.id});
    assert.deepEqual(initial.supported,['off','minimal','low','medium','high','max']);
    await assert.rejects(think({action:'set',level:'xhigh'}),/Unsupported/);
    assert.equal(session.thinkingLevel,'low');
    // Native setter clamps; our tool rejects unsupported effort before mutation.
    session.setThinkingLevel('xhigh'); assert.equal(session.thinkingLevel,'max');
    session.setThinkingLevel('low');
    assert.equal(settings.getDefaultThinkingLevel(),'low');
    onStream=async(n,options)=>{
      if(n!==1)return;
      assert.equal(options.reasoning,'low');
      // Invoke the local tool directly to isolate its native in-flight timing boundary.
      // This is not a simulation of an agent processing a tmux request.
      const receipt=await think({action:'set',level:'high'});
      assert.equal(receipt.requested,'high');
      assert.equal(receipt.effective,'high');
      assert.equal(receipt.changed,true);
      assert.equal(receipt.busy,true);
      assert.equal(receipt.inFlightChanged,false);
      assert.equal(receipt.appliesTo,'next_model_request');
      assert.equal(session.thinkingLevel,'high');
      assert.equal(options.reasoning,'low');
      assert.equal(options.signal.aborted,false);
    };
    await session.prompt('Exercise stream, local tool continuation and next-request thinking.');
    if(streamError)throw streamError;
    assert.deepEqual(calls.map(c=>c.reasoning),['low','high','medium']);
    assert.ok(calls.every(c=>!c.signal.aborted));
    assert.equal(settings.getDefaultThinkingLevel(),'low');
    assert.equal(session.model.id,model.id);
    assert.equal(session.model.provider,model.provider);
    const levels=()=>manager.getEntries().filter(e=>e.type==='thinking_level_change').map(e=>e.thinkingLevel);
    assert.deepEqual(levels().slice(-4),['max','low','high','medium']);
    const before=levels();
    assert.equal((await think({action:'set',level:'medium'})).changed,false);
    assert.deepEqual(levels(),before);
    await session.reload();
    assert.equal((await think({action:'inspect'})).effective,'medium');
    assert.deepEqual(extensionErrors,[]);
    console.log('native request reasoning: low -> high -> medium; no abort/model change; global default unchanged; native session changes recorded');
  } finally {session.dispose();}
});
