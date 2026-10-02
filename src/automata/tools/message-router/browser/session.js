/** Same-origin local browser auth only. Cookies are HttpOnly and never read here.
 * Pairing is explicit; status never opens a socket, starts an agent, or replays work.
 */
export function createBrowserSessionAuth({fetchImpl = globalThis.fetch,
                                         location = globalThis.location} = {}) {
  if (!fetchImpl || !location) throw new Error('Browser session auth is unavailable');
  const origin = new URL(location.origin);
  if (origin.protocol !== 'http:' || origin.hostname !== '127.0.0.1')
    throw new Error('Session pairing requires the authoritative local HTTP origin');
  async function request(path, value, requestState = false) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetchImpl(new URL(path, origin).href, {
        method:value === undefined ? 'GET' : 'POST', credentials:'same-origin',
        mode:'same-origin', cache:'no-store', signal:controller.signal,
        ...(value === undefined ? {} : {headers:{'Content-Type':'application/json'}, body:JSON.stringify(value)}),
      });
      if (!response.ok) throw new Error(`Session request rejected (${response.status})`);
      const result = await response.json();
      if (requestState) {
        if (!/^RP-[0-9A-F]{10}$/.test(result.request) || !Number.isFinite(result.expiresAt) ||
            !['pending','approved','redeemed','cancelled','expired'].includes(result.state) ||
            (['approved','redeemed'].includes(result.state) && typeof result.participant !== 'string'))
          throw new Error('Invalid pairing request status');
      } else if (typeof result.authenticated !== 'boolean') throw new Error('Invalid session status');
      return result;
    } finally { clearTimeout(timer); }
  }
  return {
    status:() => request('/session/status'),
    pair(code) {
      if (typeof code !== 'string' || !code || code.length > 256) throw new Error('Pairing code required');
      return request('/session/pair', {code});
    },
    forget:() => request('/session/logout', {}),
    requestPairing:capability => request('/session/request', {capability}, true),
    requestStatus:(locator, capability) => request('/session/request-status', {request:locator, capability}, true),
    cancelRequest:(locator, capability) => request('/session/request-cancel', {request:locator, capability}, true),
    redeemRequest:(locator, capability) => request('/session/request-redeem', {request:locator, capability}),
    connection(status) {
      if (!status?.authenticated || typeof status.participant !== 'string') throw new Error('Pairing expired or unavailable');
      return {wsUrl:new URL('/session/ws', origin).href.replace(/^http:/, 'ws:'), participant:status.participant};
    },
  };
}
