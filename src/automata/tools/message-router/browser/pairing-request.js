/** Short-lived requester binding, never part of a draft or public locator.
 * sessionStorage survives refresh, but cloned tabs may copy it: no tab isolation.
 * The caller owns scheduling. No internal polling, retry or connection effects.
 * Persist the attempt before redeem: an uncertain claim is never safe to retry.
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
        !['pending','approved','cancelled','redeemed','expired'].includes(value.state) ||
        (value.claimAttempted !== undefined && typeof value.claimAttempted !== 'boolean') ||
        (value.claimConfirmed !== undefined && typeof value.claimConfirmed !== 'boolean') ||
        (value.claimConfirmed && !value.claimAttempted))
      throw new Error('Invalid transient requester binding; clear this request explicitly');
    return value;
  }
  function view() {
    if (!binding) return null;
    return {request:binding.request, expiresAt:binding.expiresAt,
      // TTL ends request eligibility, not the independently-lived claimed session.
      state:binding.state === 'redeemed' || binding.claimConfirmed ? 'redeemed' :
        binding.expiresAt <= now() / 1000 ? 'expired' : binding.state,
      claimAttempted:binding.claimAttempted === true,
      claimUncertain:binding.claimAttempted === true && !binding.claimConfirmed,
      ...(binding.participant ? {participant:binding.participant} : {})};
  }
  function write(value) {
    getStorage().setItem(key, JSON.stringify(value)); // fail before issuing a new request
    binding = value;
  }
  function accept(value, captured, explicitCreate = false, claimConfirmed = false) {
    // A late HTTP completion must not overwrite a newer local requester binding.
    const current = read();
    if (binding !== captured || current?.capability !== captured.capability) return false;
    if (captured.request && captured.request !== value.request &&
        !(explicitCreate && value.state === 'pending')) throw new Error('Request changed');
    write({...captured, request:value.request, state:value.state,
      expiresAt:Math.min(captured.expiresAt, value.expiresAt),
      ...((captured.claimAttempted || current.claimAttempted) ? {claimAttempted:true} : {}),
      ...((captured.claimConfirmed || current.claimConfirmed || claimConfirmed) ? {claimConfirmed:true} : {}),
      ...(value.participant ? {participant:value.participant} : {})});
    return true;
  }
  function current() {
    if (!binding?.request || binding.expiresAt <= now() / 1000) throw new Error('Request expired or unavailable');
    return binding;
  }
  return {
    restore() { binding = read(); return view(); },
    view,
    async start() {
      if (!binding) binding = read();
      if (view()?.claimUncertain) throw new Error('Uncertain claim requires operator repair');
      if (view()?.claimAttempted || view()?.state === 'redeemed')
        throw new Error('Redeemed request requires explicit session revocation');
      if (!binding || ['expired','cancelled'].includes(view().state)) {
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
      const candidate = current();
      if (candidate.state !== 'approved' || candidate.claimAttempted)
        throw new Error('Request not approved or claim already attempted');
      write({...candidate, claimAttempted:true}); // failed persistence means zero redeem calls
      const captured = binding;
      const session = await auth.redeemRequest(captured.request, captured.capability);
      if (!session.authenticated || session.participant !== captured.participant)
        throw new Error('Claim did not confirm the approved page session');
      // A failed/uncertain redeem retains the marker, even past TTL and reload.
      accept({...captured, state:'redeemed'}, captured, false, true);
      return session;
    },
    confirmSession(status) {
      // Another page's cookie is not evidence that this claim delivered its cookie.
      if (view()?.claimUncertain && status.authenticated &&
          binding.participant && status.participant === binding.participant)
        write({...binding, state:'redeemed', claimConfirmed:true});
    },
    clearExpired({revokedParticipant} = {}) {
      // Caller may attest the matched, previously authenticated participant ONLY
      // after successful explicit logout. TTL/missing cookies cannot attest this.
      if (view()?.claimUncertain) throw new Error('Uncertain claim requires operator repair');
      if ((view()?.claimAttempted || view()?.state === 'redeemed') &&
          (!binding.participant || revokedParticipant !== binding.participant))
        throw new Error('Redeemed request requires explicit session revocation');
      if (binding && !['expired','cancelled','redeemed'].includes(view().state))
        throw new Error('Cancel the outstanding request before clearing it');
      getStorage().removeItem(key); binding = null;
    },
  };
}
