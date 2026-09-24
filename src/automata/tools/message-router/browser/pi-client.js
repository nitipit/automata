/** Chat/context application adapter over the generic router. UI components remain independent.
 * Credentials identify this page; `to` explicitly selects one authorized Pi participant.
 * The legacy callback/sendMessage API is retained, but v2 request IDs and Pi route IDs differ.
 */
import {createMessageRouterClient} from './client.js';
import {validateDelivery, requireId} from './protocol.js';

/** @deprecated Use createMessageRouterChatClient; retained for existing page integrations. */
export {createMessageRouterChatClient as createAgentRouterChatClient};

export function createMessageRouterChatClient({to, onMessage = () => {}, onState = () => {},
                                            onDelivery = () => {}, WebSocketImpl} = {}) {
  requireId(to, 'Pi destination');
  let pendingId;
  const contexts = new Set();
  const router = createMessageRouterClient({WebSocketImpl,onState});

  function submit(payload, metadata, context) {
    if (context && contexts.size >= 32) throw new Error('Context request capacity reached');
    if (!context && pendingId) throw new Error('A user message is already pending');
    let settled = false, admitted = false;
    const sent = router.send(to, payload, {metadata,onResponse:packet => {
      const id = packet.requestId;
      if (packet.final || packet.type === 'route_closed') settled = true;
      if (packet.type === 'route_closed') {
        if (context) { contexts.delete(id); onDelivery({id,status:'uncertain',details:{reason:packet.reason}}); }
        else { pendingId = undefined; onState({status:'disconnected',pendingId:id,uncertain:true}); }
        return;
      }
      const receipt = packet.metadata?.pi;
      if (context && receipt?.type === 'context_result') {
        if (packet.final) contexts.delete(id);
        onDelivery({id,status:receipt.status,details:receipt.details});
      } else if (!context && receipt?.type === 'admitted') { admitted = true; onState({status:'admitted',id}); }
      else if (receipt?.type === 'rejected') {
        if (context) { contexts.delete(id); onDelivery({id,status:'rejected',details:{reason:receipt.error?.message}}); }
        else { pendingId = undefined; onState({status:'rejected',id,error:receipt.error}); }
      } else if (!context && receipt?.type === 'reply' && packet.final) {
        pendingId = undefined;
        onState({status:'replied',id,replyId:packet.id});
        onMessage({v:1,kind:'reply',id:packet.id,correlationId:id,payload:packet.payload});
      } else {
        settled = true;
        if (context) { contexts.delete(id); onDelivery({id,status:'uncertain',details:{reason:'Unexpected Pi receipt'}}); }
        else { if (pendingId === id) pendingId = undefined; onState({status:'error',id,uncertain:true,error:{code:'protocol',message:'Unexpected Pi receipt'}}); }
        if (!packet.final) void router.cancel(id).catch(() => {});
      }
    }});
    if (!settled) { if (context) contexts.add(sent.id); else pendingId = sent.id; }
    void sent.accepted.then(result => {
      if (result.status === 'forwarded' && !context && !admitted && pendingId === sent.id)
        onState({status:'accepted',id:sent.id,transport:'accepted'});
    }, error => {
      if (settled) return;
      settled = true;
      if (context) { contexts.delete(sent.id); onDelivery({id:sent.id,status:'rejected',details:{reason:error.message}}); }
      else { pendingId = undefined; onState({status:'rejected',id:sent.id,error:{code:'route',message:error.message}}); }
    });
    if (!context && !settled && !admitted) onState({status:'sending',id:sent.id});
    return {id:sent.id};
  }

  return {
    connect:credentials => router.connect(credentials),
    sendMessage(payload, options) {
      const delivery = options === undefined ? undefined : validateDelivery(options);
      return submit(payload, delivery ? {pi:{delivery}} : {}, delivery?.role === 'context');
    },
    inspectContext(slot) {
      if (slot !== undefined) requireId(slot,'context slot');
      return submit(null,{pi:{kind:'context_control',action:'inspect',...(slot === undefined ? {} : {slot})}},true);
    },
    clearContext(slot) {
      if (slot !== undefined) requireId(slot,'context slot');
      return submit(null,{pi:{kind:'context_control',action:'clear',...(slot === undefined ? {} : {slot})}},true);
    },
    close() { router.close(); pendingId = undefined; contexts.clear(); },
    isConnected:router.isConnected,
    getPendingId:() => pendingId,
    getSessionId:() => to, // compatibility accessor: destination, never a page directory
  };
}
