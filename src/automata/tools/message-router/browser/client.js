/** Explicit, authenticated v2 requests. No automatic reconnect or message replay.
 * send() returns {id, accepted}; responses can race the accepted transport promise.
 * respond() uses the received message.id, never a participant name, as its capability.
 * Call close() when finished; reconnect invalidates old pending work.
 */
import {parseFrame, serializePayload, serializeMetadata, requireId, isRecord} from './protocol.js';
export {createAgentBrowserBridgeClient} from './legacy-client.js';
export {serializePayload, validateDelivery} from './protocol.js';

/** @deprecated Use createMessageRouterClient; retained for existing page integrations. */
export {createMessageRouterClient as createAgentRouterClient};

export function createMessageRouterClient({
  WebSocketImpl = globalThis.WebSocket,
  onMessage = () => {}, onResponse = () => {}, onState = () => {},
} = {}) {
  let socket, generation = 0, connected = false, opening;
  const pending = new Map(), outgoing = new Map(), incoming = new Set();

  function notify(callback, value) {
    // Application callbacks are not protocol parsing, and must not throw into it.
    try { Promise.resolve(callback(value)).catch(() => onState({status:'handler_error'})); }
    catch { onState({status:'handler_error'}); }
  }
  function invalidate(reason) {
    generation++;
    connected = false;
    const old = socket;
    socket = undefined;
    if (opening) { clearTimeout(opening.timer); opening.reject(new Error(reason)); opening = undefined; }
    for (const request of pending.values()) { clearTimeout(request.timer); request.reject(new Error(reason)); }
    pending.clear();
    const lost = [...outgoing.entries()];
    outgoing.clear(); incoming.clear();
    old?.close();
    for (const [id, request] of lost) notify(request.callback, {type:'route_closed', requestId:id, id:request.routeId, uncertain:true, reason});
    onState({status:'disconnected', uncertain:lost.length > 0});
  }
  function connect({wsUrl, participant, token, sessionId}) {
    requireId(participant, 'participant');
    if (typeof token !== 'string' || !token || token.length > 256) throw new Error('Invalid participant token');
    if (sessionId !== undefined) requireId(sessionId, 'session id');
    const url = new URL(wsUrl);
    if (!['ws:', 'wss:'].includes(url.protocol) || url.username || url.password) throw new Error('Invalid WebSocket URL');
    if (!WebSocketImpl) throw new Error('WebSocket is unavailable');
    invalidate('Reconnected; previous delivery uncertain');
    const epoch = generation;
    const currentSocket = new WebSocketImpl(wsUrl);
    socket = currentSocket;
    const current = () => socket === currentSocket && generation === epoch;
    const promise = new Promise((resolve, reject) => {
      opening = {resolve, reject, timer:setTimeout(() => {
        if (current()) invalidate('Authentication timeout');
      }, 5000)};
    });
    currentSocket.onmessage = event => {
      if (!current()) return;
      try {
        const packet = parseFrame(event.data);
        if (packet.type === 'error') throw new Error('Router protocol error');
        if (packet.v !== 2) throw new Error('Expected router protocol version 2');
        if (packet.type === 'hello_ack') {
          if (!opening || packet.participant !== participant || !['page','agent'].includes(packet.kind)) throw new Error('Invalid authentication acknowledgment');
          connected = true;
          const ready = opening; opening = undefined; clearTimeout(ready.timer);
          ready.resolve(packet);
          onState({status:'connected', participant, kind:packet.kind});
          return;
        }
        if (!connected) throw new Error('Router message before authentication');
        if (packet.type === 'result') {
          const request = pending.get(packet.requestId);
          if (!request) return;
          pending.delete(packet.requestId); clearTimeout(request.timer);
          if (packet.status === 'rejected') request.reject(new Error(String(packet.error ?? 'rejected')));
          else request.resolve(packet);
          return;
        }
        if (packet.type === 'message' || packet.type === 'response') {
          requireId(packet.id, 'route id');
          if (!isRecord(packet.from) || !['page','agent'].includes(packet.from.kind)) throw new Error('Invalid sender provenance');
          requireId(packet.from.id, 'sender');
          if (!Object.hasOwn(packet, 'payload')) throw new Error('Missing payload');
          serializePayload(packet.payload); serializeMetadata(packet.metadata);
          if (packet.type === 'message') {
            if (packet.to !== participant || typeof packet.expectReply !== 'boolean') throw new Error('Invalid destination');
            if (packet.expectReply) {
              if (incoming.size >= 64 || incoming.has(packet.id)) throw new Error('Incoming capacity or duplicate');
              incoming.add(packet.id);
            }
            notify(onMessage, packet);
          } else {
            const request = outgoing.get(packet.requestId);
            if (!request) return; // completed/canceled, never attach to a different request
            if (request.to !== packet.from.id || typeof packet.final !== 'boolean' || (request.routeId && request.routeId !== packet.id)) throw new Error('Invalid response correlation');
            request.routeId = packet.id;
            if (packet.final) outgoing.delete(packet.requestId);
            notify(request.callback, packet);
          }
          return;
        }
        if (packet.type === 'route_closed') {
          incoming.delete(packet.id);
          const request = outgoing.get(packet.requestId);
          if (request && (!request.routeId || request.routeId === packet.id)) {
            outgoing.delete(packet.requestId);
            notify(request.callback, packet);
          }
          return;
        }
        throw new Error('Unknown router packet');
      } catch { invalidate('Malformed router response; delivery uncertain'); }
    };
    currentSocket.onclose = () => { if (current()) invalidate('Connection closed; delivery uncertain'); };
    currentSocket.onerror = () => { if (current()) invalidate('Connection failed; delivery uncertain'); };
    currentSocket.addEventListener('open', () => {
      if (!current()) return;
      try { currentSocket.send(JSON.stringify({v:2, type:'hello', participant, token, ...(sessionId === undefined ? {} : {sessionId})})); }
      catch { invalidate('Authentication write failed'); }
    }, {once:true});
    return promise;
  }

  function rpc(type, fields = {}, id = crypto.randomUUID()) {
    if (!connected || socket?.readyState !== 1) throw new Error('Router is disconnected');
    if (pending.size >= 64) throw new Error('Transport request capacity reached');
    const encoded = JSON.stringify({v:2, type, requestId:id, ...fields});
    if (new TextEncoder().encode(encoded).byteLength > 64 * 1024) throw new Error('Frame exceeds 64 KiB');
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => invalidate('Transport timeout; delivery uncertain'), 5000);
      pending.set(id, {resolve, reject, timer});
      try { socket.send(encoded); }
      catch { invalidate('Transport write failed; delivery uncertain'); }
    });
  }

  function send(to, payload, {metadata = {}, expectReply = true, onResponse:callback = onResponse} = {}) {
    requireId(to, 'destination');
    serializePayload(payload); serializeMetadata(metadata);
    if (typeof expectReply !== 'boolean') throw new Error('expectReply must be boolean');
    if (outgoing.size >= 64) throw new Error('Pending reply capacity reached');
    const id = crypto.randomUUID();
    const request = {to, callback, routeId:undefined};
    if (expectReply) outgoing.set(id, request);
    let accepted;
    try { accepted = rpc('route', {to, payload, metadata, expectReply}, id); }
    catch (error) { outgoing.delete(id); throw error; }
    accepted = accepted.then(result => {
      if (result.status === 'forwarded') {
        if (request.routeId && request.routeId !== result.routeId) {
          invalidate('Invalid route acknowledgment'); throw new Error('Delivery uncertain');
        }
        request.routeId = result.routeId;
      } else {
        outgoing.delete(id);
        notify(callback, {type:'route_closed', requestId:id, id:result.routeId, uncertain:true, reason:result.status});
      }
      return result;
    }, error => { outgoing.delete(id); throw error; });
    return {id, accepted};
  }

  function respond(id, payload, {metadata = {}, final = true} = {}) {
    requireId(id, 'route id'); serializePayload(payload); serializeMetadata(metadata);
    if (typeof final !== 'boolean') throw new Error('final must be boolean');
    if (!incoming.has(id)) throw new Error('No matching inbound reply capability');
    const accepted = rpc('respond', {routeId:id, payload, metadata, final});
    if (final) incoming.delete(id); // synchronous claim; deterministic preflight errors retain it
    return accepted;
  }

  function cancel(id) {
    const request = outgoing.get(id);
    if (!request?.routeId) throw new Error('No acknowledged pending route');
    outgoing.delete(id);
    return rpc('cancel', {routeId:request.routeId});
  }

  return {connect, send, respond, cancel, status:() => rpc('status'),
    close:() => invalidate('Closed explicitly; delivery uncertain'), isConnected:() => connected};
}
