window.failures = [];
window.onerror = message => failures.push(String(message));
window.addEventListener("unhandledrejection", event => failures.push(String(event.reason)));
class FakeSocket extends EventTarget {
  static OPEN = 1;
  readyState = 1;
  sent = [];
  constructor(url) {
    super();
    const chat = new URL(url).pathname === "/chat";
    if (chat) window.sock = this; else window.bridgeSock = this;
    setTimeout(() => {
      this.dispatchEvent(new Event("open"));
      if (chat) this.emit({ type: "snapshot", messages: [], state: { status: "idle" }, dialogs: [] });
    }, 5);
  }
  close() { this.readyState = 3; this.dispatchEvent(new Event("close")); }
  send(value) { this.sent.push(JSON.parse(value)); }
  emit(value) { this.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(value) })); }
}
window.WebSocket = FakeSocket;
const originalFetch = window.fetch.bind(window);
window.fetch = (url, options) => String(url) === '/chat/connection'
  ? Promise.resolve(new Response('{"ready":true}', {status:200}))
  : originalFetch(url, options);
