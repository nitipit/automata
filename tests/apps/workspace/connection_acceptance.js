// Executed in isolated Chromium with mock_router.js. MOCK identity/transport evidence only.
export async function verifyConnection() {
  const { AgentConnection } = await import("/modules/agent/connection.js");
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const binding = { conversationId: "conversation-aster", agentId: "agent-automata",
    displayName: "Automata", to: "workspace-agent", credentials: {
      wsUrl: "ws://127.0.0.1:8791/ws", participant: "mock-page", token: "mock-only" } };
  const events = [];
  const connection = new AgentConnection(value => events.push(value));
  await connection.initialize(async () => ({ binding }));
  assert(!connection.isBound("conversation-aster"), "Initialization must not connect");
  await Promise.all([connection.connect(), connection.connect()]);
  assert(mockRouter.connections === 1, "Concurrent connect creates one socket");
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
  assert(connection.phase === "disconnected", "Offline destination is not connected");
  const invalid = new AgentConnection();
  rejected = false;
  try { await invalid.initialize(async () => ({ binding: { ...binding, to: "other-agent" } })); }
  catch { rejected = true; }
  assert(rejected, "Arbitrary online participant cannot become assigned agent");
  return { mock: true, requests: mockRouter.requests.length, events: events.length,
    checks: "assignment, double-connect, offline, response provenance, runtime change, no-history/no-replay" };
}
