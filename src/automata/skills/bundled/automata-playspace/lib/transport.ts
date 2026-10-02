/** Lifetime facade only. Router owns packets, auth, correlation and capabilities. */
type Packet = Record<string, any>;
type SendOptions = {
  metadata?: Record<string, any>;
  expectReply?: boolean;
  onResponse?: (packet: Packet) => void;
  isCurrent?: () => boolean;
};
type RouterClient = {
  connect(credentials: any): Promise<unknown>;
  connectSession(session: any): Promise<unknown>;
  send(to: string, payload: unknown, options: Omit<SendOptions, "isCurrent">): {
    id: string; accepted: Promise<any>;
  };
  respond(id: string, payload: unknown, options?: any): Promise<any>;
  isConnected(): boolean;
  close(): void;
};

export function createPlayspaceRouter({ createClient, onState = () => {}, onMessage = () => {} }: {
  createClient(options: { onState(packet: Packet): void; onMessage(packet: Packet): void }): RouterClient;
  onState?: (packet: Packet) => void;
  onMessage?: (packet: Packet) => void;
}) {
  let alive = true;
  let generation = 0;
  let client: RouterClient | undefined;
  function retire() {
    generation++; // close can synchronously emit callbacks; invalidate first
    const previous = client;
    client = undefined;
    previous?.close();
  }
  async function open(method: "connect" | "connectSession", credentials: unknown) {
    if (!alive) throw new Error("Router facade is disposed");
    retire();
    const epoch = generation;
    const current = () => alive && epoch === generation;
    try {
      const next = createClient({
        onState: packet => { if (current()) onState(packet); },
        onMessage: packet => { if (current()) onMessage(packet); },
      });
      client = next;
      await next[method](credentials);
      return current() && next.isConnected();
    } catch {
      if (!current()) return false;
      retire();
      throw new Error("Router connection failed; explicit reconnection required");
    }
  }
  return {
    connect: (credentials: unknown) => open("connect", credentials),
    connectSession: (session: unknown) => open("connectSession", session),
    disconnect() {
      retire();
      if (alive) onState({ status: "disconnected" });
    },
    send(to: string, payload: unknown, options: SendOptions = {}) {
      if (!alive || !client?.isConnected()) throw new Error("Router is disconnected");
      const epoch = generation;
      const { isCurrent = () => true, onResponse = () => {}, ...routerOptions } = options;
      return client.send(to, payload, { ...routerOptions, onResponse(packet) {
        if (alive && epoch === generation && isCurrent()) onResponse(packet);
      } });
    },
    respond(id: string, payload: unknown, options?: unknown) {
      if (!alive || !client?.isConnected()) throw new Error("Router is disconnected");
      return client.respond(id, payload, options);
    },
    isConnected: () => alive && !!client?.isConnected(),
    dispose() { if (alive) { alive = false; retire(); } },
  };
}
