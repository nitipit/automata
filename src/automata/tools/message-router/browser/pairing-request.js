/** Short-lived requester binding, never part of a draft or public locator.
 * sessionStorage survives refresh, but cloned tabs may copy it: no tab isolation.
 * All network operations are explicit. No polling, retry, auto-claim or connect.
 */
export function createPairingRequest({auth, location = globalThis.location,
  getStorage = () => globalThis.sessionStorage, crypto = globalThis.crypto,
  now = () => Date.now()} = {}) {
  const key = `automata-router-request-v1:${new URL('.', location.href).href}`;
  let binding = null;
  function read() {
    const raw = getStorage().getItem(key);
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (!value || !/^[0-9a-f]{64}$/.test(value.capability) ||
        !Number.isFinite(value.expiresAt) || value.expiresAt > now() / 1000 + 300 ||
        (value.request !== undefined && !/^RP-[0-9A-F]{10}$/.test(value.request)) ||
        !['pending','approved','cancelled','redeemed','expired'].includes(value.state))
      throw new Error('Invalid transient requester binding; clear this request explicitly');
    return value;
  }
  function view() {
    if (!binding) return null;
    return {request:binding.request, expiresAt:binding.expiresAt,
      state:binding.expiresAt <= now() / 1000 ? 'expired' : binding.state,
      ...(binding.participant ? {participant:binding.participant} : {})};
  }
  function write(value) {
    getStorage().setItem(key, JSON.stringify(value)); // fail before issuing a new request
    binding = value;
  }
  function accept(value, captured, explicitCreate = false) {
    // A late HTTP completion must not overwrite a newer local requester binding.
    const current = read();
    if (binding !== captured || current?.capability !== captured.capability) return false;
    if (captured.request && captured.request !== value.request &&
        !(explicitCreate && value.state === 'pending')) throw new Error('Request changed');
    write({...captured, request:value.request, state:value.state,
      expiresAt:Math.min(captured.expiresAt, value.expiresAt),
      ...(value.participant ? {participant:value.participant} : {})});
    return true;
  }
  function current() {
    if (!binding?.request || view().state === 'expired') throw new Error('Request expired or unavailable');
    return binding;
  }
  return {
    restore() { binding = read(); return view(); },
    view,
    async start() {
      if (!binding) binding = read();
      if (!binding || ['expired','cancelled','redeemed'].includes(view().state)) {
        const bytes = crypto.getRandomValues(new Uint8Array(32));
        const capability = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
        write({capability, state:'pending', expiresAt:now() / 1000 + 300});
      }
      const captured = binding;
      const value = await auth.requestPairing(captured.capability);
      // An explicit create after service restart may return a new pending locator.
      // Preserve the original local deadline; never carry approval to that locator.
      accept(value, captured, true);
      return view();
    },
    async check() {
      const captured = current();
      const value = await auth.requestStatus(captured.request, captured.capability);
      accept(value, captured);
      return view();
    },
    async cancel() {
      const captured = current();
      const value = await auth.cancelRequest(captured.request, captured.capability);
      accept(value, captured);
      return view();
    },
    async claim() {
      const captured = current();
      if (captured.state !== 'approved') throw new Error('Request not approved');
      const session = await auth.redeemRequest(captured.request, captured.capability);
      // Keep a terminal, bounded tombstone for explicit lost-response/status recovery.
      accept({...captured, state:'redeemed'}, captured);
      return session;
    },
    clearExpired() {
      // Explicit local recovery only; never implies server cancellation or logout.
      if (binding && !['expired','cancelled','redeemed'].includes(view().state))
        throw new Error('Cancel the outstanding request before clearing it');
      getStorage().removeItem(key); binding = null;
    },
  };
}
