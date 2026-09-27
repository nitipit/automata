// Mechanical browser test double ONLY. This is not evidence of a real agent.
window.mockRouter = { requests: [], mode: "reply", sequence: 0, connections: 0,
  sessionId: "mock-session", participant: "workspace-agent", online: true };
window.WebSocket = class MockWebSocket extends EventTarget {
  readyState = 1;
  constructor() {
    super();
    window.mockRouter.connections++;
    window.mockRouter.socket = this;
    queueMicrotask(() => this.dispatchEvent(new Event("open")));
  }
  emit(packet) { this.onmessage?.({ data: JSON.stringify({ v: 2, ...packet }) }); }
  send(encoded) {
    const frame = JSON.parse(encoded);
    if (frame.type === "hello") {
      queueMicrotask(() => this.emit({ type: "hello_ack", participant: frame.participant, kind: "page" }));
    } else if (frame.type === "status") {
      queueMicrotask(() => this.emit({ type: "result", requestId: frame.requestId,
        status: "connected", destinations: [{ id: "workspace-agent", kind: "agent", connected: window.mockRouter.online }] }));
    } else if (frame.type === "route") {
      window.mockRouter.requests.push(frame);
      const routeId = `mock-route-${++window.mockRouter.sequence}`;
      queueMicrotask(() => {
        this.emit({ type: "result", requestId: frame.requestId, routeId, status: "forwarded" });
        if (window.mockRouter.mode === "disconnect") { this.close(); return; }
        if (window.mockRouter.mode === "hold") return;
        const content = frame.payload.kind === "workspace.form-submit"
          ? [{ id: "ack", type: "text", version: 1, data: { text: "Mock acknowledgement: structured values received" } }]
          : [{ id: "intro", type: "text", version: 1, data: { text: "Mock agent reply (not live evidence)" } },
             { id: "task-form", type: "form", version: 1, data: { title: "A small task", submitLabel: "Send details", fields: [
               { name: "title", kind: "text", label: "Task title", required: true, maxLength: 100 },
               { name: "outcome", kind: "text", label: "Desired outcome", required: true, maxLength: 500 },
             ] } }];
        this.emit({ type: "response", id: routeId, requestId: frame.requestId, final: true,
          from: { id: window.mockRouter.participant, kind: "agent", sessionId: window.mockRouter.sessionId }, metadata: {}, payload: { content } });
      });
    }
  }
  close() { if (this.readyState !== 3) { this.readyState = 3; this.onclose?.(); } }
};
