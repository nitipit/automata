/** Same-origin local browser auth only. Cookies are HttpOnly and never read here.
 * Pairing is explicit; status never opens a socket, starts an agent, or replays work.
 */
export function createBrowserSessionAuth({fetchImpl = globalThis.fetch,
                                         location = globalThis.location} = {}) {
  if (!fetchImpl || !location) throw new Error('Browser session auth is unavailable');
  const origin = new URL(location.origin);
  if (origin.protocol !== 'http:' || origin.hostname !== '127.0.0.1')
    throw new Error('Session pairing requires the authoritative local HTTP origin');
  async function request(path, value) {
    const response = await fetchImpl(new URL(path, origin).href, {
      method:value === undefined ? 'GET' : 'POST', credentials:'same-origin',
      mode:'same-origin', cache:'no-store',
      ...(value === undefined ? {} : {headers:{'Content-Type':'application/json'}, body:JSON.stringify(value)}),
    });
    if (!response.ok) throw new Error(`Session request rejected (${response.status})`);
    const result = await response.json();
    if (typeof result.authenticated !== 'boolean') throw new Error('Invalid session status');
    return result;
  }
  return {
    status:() => request('/session/status'),
    pair(code) {
      if (typeof code !== 'string' || !code || code.length > 256) throw new Error('Pairing code required');
      return request('/session/pair', {code});
    },
    forget:() => request('/session/logout', {}),
    connection(status) {
      if (!status?.authenticated || typeof status.participant !== 'string') throw new Error('Pairing expired or unavailable');
      return {wsUrl:new URL('/session/ws', origin).href.replace(/^http:/, 'ws:'), participant:status.participant};
    },
  };
}
