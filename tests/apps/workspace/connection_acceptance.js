// Executed in isolated Chromium with mock_router.js. MOCK identity/transport evidence only.
export async function verifyConnection() {
  const { AgentConnection } = await import("/modules/agent/connection.js");
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const binding = { conversationId: "conversation-aster", agentId: "agent-automata",
    displayName: "Automata", to: "workspace-agent", credentials: {
      wsUrl: "ws://127.0.0.1:8791/ws", participant: "mock-page", token: "mock-only" } };
  const events = [];
  const connection = new AgentConnection(value => events.push(value));
  const beforeConnections = mockRouter.connections;
  const launches = [];
  const api = async (path, options) => {
    if (path === "/api/agent-binding") return { binding };
    if (options?.method === "POST") {
      launches.push({ path, body: JSON.parse(options.body) });
      return { configured: true, phase: "starting", action: null };
    }
    return { configured: true, phase: "offline", action: "start" };
  };
  await connection.initialize(api);
  assert(connection.isBound("conversation-aster"), "Initialization auto-connects page only");
  assert(launches.length === 0, "Opening page never launches agent");
  await Promise.all([connection.connect(), connection.connect()]);
  assert(mockRouter.connections === beforeConnections + 1, "Concurrent connect creates one socket");
  assert(connection.isBound("conversation-aster"), "Assigned conversation connects");
  assert(!connection.isBound("conversation-mira"), "Other history is not bound");
  assert(mockRouter.requests.length === 0, "Connect never sends history or requests");
  assert(connection.lastSession === null, "Connection cannot infer runtime session");
  const request = { kind: "workspace.message", version: 1, conversationId: "conversation-aster",
    agentId: "agent-automata", content: [{ id: "text", type: "text", version: 1,
      data: { text: "Synthetic connection test only" } }] };
  for (const bad of [{ ...request, conversationId: "conversation-mira" },
    { ...request, agentId: "other-agent" }]) {
    let rejected = false;
    try { await connection.request(bad); } catch { rejected = true; }
    assert(rejected, "Wrong assignment must reject before routing");
  }
  assert(mockRouter.requests.length === 0, "Rejected assignment discloses nothing");
  await connection.request(request);
  assert(connection.lastSession === "mock-session", "Runtime comes from response provenance");
  mockRouter.sessionId = "replacement-session";
  await connection.request(request);
  assert(connection.lastSession === "replacement-session", "Changed runtime is displayed, not hidden");
  assert(connection.binding.agentId === "agent-automata", "Runtime change cannot reassign stable identity");
  connection.disconnect();
  assert(connection.lastSession === null && !connection.isBound("conversation-aster"), "Disconnect clears live evidence");
  const before = mockRouter.requests.length;
  await connection.connect();
  assert(mockRouter.requests.length === before && connection.lastSession === null, "Reconnect never replays or claims continuity");
  mockRouter.participant = "unassigned-agent";
  let rejected = false;
  try { await connection.request(request); } catch { rejected = true; }
  assert(rejected && !connection.isBound("conversation-aster"), "Wrong responder is rejected");
  mockRouter.participant = "workspace-agent";
  mockRouter.sessionId = null;
  await connection.connect();
  rejected = false;
  try { await connection.request(request); } catch { rejected = true; }
  assert(rejected, "Missing runtime provenance rejected");
  mockRouter.online = false;
  await connection.connect();
  assert(connection.phase === "connected" && !connection.available,
    "Offline agent keeps healthy router connected");
  await Promise.all([connection.launch(), connection.launch()]);
  assert(launches.length === 1, "Double-click launches only once");
  assert(launches[0].body.agentId === binding.agentId, "Launch names only configured identity");
  assert(mockRouter.requests.length === before + 2, "Lifecycle checks never replay messages");
  mockRouter.online = true;
  await connection.check();
  assert(connection.available, "Presence check detects agent becoming available");
  const requestsBeforeRecovery = mockRouter.requests.length;
  connection.client.close();
  await new Promise(resolve => setTimeout(resolve, 1200));
  assert(connection.available, "Background recovery restores page transport");
  assert(mockRouter.requests.length === requestsBeforeRecovery, "Background recovery never replays");
  connection.retries = 6;
  connection.client.close();
  assert(connection.phase === "disconnected" && !connection.retryTimer,
    "Exhausted retry burst pauses instead of looping forever");
  connection.wake();
  await new Promise(resolve => setTimeout(resolve, 50));
  assert(connection.available, "Network wake starts a new bounded transport recovery");
  assert(mockRouter.requests.length === requestsBeforeRecovery, "Network wake never replays");
  connection.disconnect();
  const invalid = new AgentConnection();
  rejected = false;
  try { await invalid.initialize(async () => ({ binding: { ...binding, to: "other-agent" } })); }
  catch { rejected = true; }
  assert(rejected, "Arbitrary online participant cannot become assigned agent");
  return { mock: true, requests: mockRouter.requests.length, events: events.length,
    checks: "auto-connect, explicit single launch, offline healthy router, background recovery, assignment, provenance, no-history/no-replay" };
}
