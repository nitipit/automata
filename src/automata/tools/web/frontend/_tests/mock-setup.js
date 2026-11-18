window.failures = [];
window.onerror = message => failures.push(String(message));
window.addEventListener("unhandledrejection", event => failures.push(String(event.reason)));
class FakeSocket extends EventTarget {
  static OPEN = 1;
  readyState = 1;
  sent = [];
  constructor(url) {
    super();
    const target = new URL(url);
    this.ticket = target.searchParams.get("token");
    const chat = target.pathname === "/sessions/browser-fixture/chat";
    if (chat) window.sock = this; else window.bridgeSock = this;
    setTimeout(() => {
      this.dispatchEvent(new Event("open"));
      if (chat) this.emit({ type: "snapshot", messages: [], state: { status: "idle" }, dialogs: [] });
    }, 5);
  }
  close() { this.readyState = 3; this.dispatchEvent(new Event("close")); }
  send(value) { this.sent.push(JSON.parse(value)); }
  emit(value) {
    if (value.type === "snapshot") value.state = { sessionId: "browser-fixture", ...value.state };
    this.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(value) }));
  }
}
window.WebSocket = FakeSocket;
const originalFetch = window.fetch.bind(window);
window.fetch = (url, options) => {
  if (String(url) !== '/sessions/browser-fixture/chat/connection') return originalFetch(url, options);
  window.fixtureAdmissionProbe = options.headers.Authorization === 'Bearer synthetic' &&
    !window.awr && !location.hash;
  return Promise.resolve(new Response('{"ticket":"fixture-ticket"}', {status:200}));
};
