// Opt-in: published SDK/owned relay, actual Pi loader + native message routing.
// No provider is constructed. Final run/queue collaborators are intentionally inert;
// message_end is explicitly emitted, not evidence of a full CLI/agent lifecycle.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { findPackageJSON } from "node:module";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const root = process.env.PI_EXTENSION_TEST_ROOT;
const piRoot = process.env.PI_TEST_PACKAGE_ROOT;
assert.ok(root && piRoot, "Use nodalwire_live_trial.py with a prepared repository-source bundle");
const clientManifest = findPackageJSON("@devcapsule/nodalwire-client", pathToFileURL(join(root, "package.json")));
const { Node, ReceiptTimeout } = await import(pathToFileURL(join(dirname(clientManifest), "dist/index.js")));
const { loadExtensions } = await import(pathToFileURL(join(piRoot, "dist/core/extensions/loader.js")));
const { AgentSession, SessionManager } = await import(pathToFileURL(join(piRoot, "dist/index.js")));
const { ExtensionRunner } = await import(pathToFileURL(join(piRoot, "dist/core/extensions/runner.js")));
const { encodeMessage, decodeMessage } = await import(pathToFileURL(join(root, "protocol.ts")));
const endpoint = process.env.NODALWIRE_TRIAL_ENDPOINT;
const protectedEndpoint = process.env.NODALWIRE_TRIAL_PROTECTED_ENDPOINT;
const credential = process.env.NODALWIRE_TRIAL_JOIN_TOKEN;
const credentialConfig = process.env.NODALWIRE_TRIAL_CREDENTIALS_CONFIG;
const ID = /^[a-f0-9]{32}$/;
const message = content => ({ content, display: true });
const receive = node => node.receive({ signal: AbortSignal.timeout(3000) });
const outcome = promise => promise.then(value => ({ value }), error => ({ error }));
const rejectsCode = (promise, code) => assert.rejects(promise, error => error.code === code);
const waitFor = async predicate => {
  const deadline = performance.now() + 3000;
  while (!predicate()) {
    assert.ok(performance.now() < deadline, "bounded wait expired");
    await new Promise(resolve => setTimeout(resolve, 5));
  }
};
const empty = node => assert.rejects(
  node.receive({ signal: AbortSignal.timeout(100) }), error => error.name === "TimeoutError",
);
// Test only the stable safe output contract, not an internal Error subclass/shape.
const safeError = (error, expected) => {
  assert.ok(error instanceof Error, "operation rejected with an Error");
  const diagnostic = `${error.message} ${JSON.stringify(error)}`;
  for (const secret of [credential, process.env.NODALWIRE_TRIAL_WRONG_TOKEN, "PRIVATE-ABORT-REASON", "RAW-CREDENTIAL-MUST-NOT-BE-ACCEPTED"]) {
    assert.ok(!secret || !diagnostic.includes(secret), "diagnostic must not expose credential/abort data");
  }
  if (expected) assert.match(diagnostic, expected);
  return true;
};
const rejectsSafe = (promise, expected) => assert.rejects(promise, error => safeError(error, expected));
const receipt = (result, expected) => {
  for (const [key, value] of Object.entries(expected)) assert.equal(result.details[key], value, key);
};

assert.equal(JSON.parse(await readFile(clientManifest, "utf8")).version, "0.3.0");
assert.equal(JSON.parse(await readFile(join(piRoot, "package.json"), "utf8")).version, process.env.PI_TEST_EXPECTED_VERSION);
for (const address of [endpoint, protectedEndpoint]) {
  assert.match(address, /^tcp:\/\/127\.0\.0\.1:\d+$/);
  assert.ok(!address.endsWith(":5555") && !address.endsWith(":5556"), "owned ephemeral endpoints only");
}
assert.ok(credential && credentialConfig, "owned fixture credential bindings required");

/** Real extension factory/API and installed routing; only terminal collaborators inert. */
async function withPi(run) {
  const cwd = process.cwd(); // Owned artifact directory, not repository/user config.
  const loaded = await loadExtensions([join(root, "index.ts")], cwd);
  assert.deepEqual(loaded.errors, []);
  assert.equal(loaded.extensions.length, 1);
  const extension = loaded.extensions[0];
  assert.deepEqual([...extension.tools.keys()].sort(), [
    "nodalwire_connection", "nodalwire_network", "nodalwire_reply", "nodalwire_request", "nodalwire_send",
  ]);
  assert.ok(extension.flags.has("nodalwire-credentials"));
  // Equivalent to an operator-selected CLI flag, not an agent-supplied file path.
  loaded.runtime.flagValues.set("nodalwire-credentials", credentialConfig);
  const notices = [], received = [], routed = [], routingPromises = [], routingErrors = [];
  const fake = {
    isStreaming: false, _isEmittingAgentSettled: false,
    _pendingNextTurnMessages: [], _pendingCustomMessages: [],
    agent: {
      steer: message => routed.push({ mode: "steer", message }),
      followUp: message => routed.push({ mode: "followUp", message }),
    },
    _appendCustomMessage: message => routed.push({ mode: "append", message }),
    _startRun: async ({ message }) => routed.push({ mode: "wake", message }),
  };
  loaded.runtime.sendMessage = (message, options) => {
    received.push({ message, options });
    // Retain/await every routing promise. Rejections are captured immediately to
    // avoid unhandled rejections before the asynchronous receive fence completes.
    const routed = AgentSession.prototype.sendCustomMessage.call(fake, message, options);
    routingPromises.push(Promise.resolve(routed).catch(error => routingErrors.push(error)));
  };
  const runner = new ExtensionRunner(loaded.extensions, loaded.runtime, cwd, SessionManager.inMemory(), {});
  runner.setUIContext({ notify: (...args) => notices.push(args), setStatus() {} });
  const errors = [];
  runner.onError(error => errors.push(error));
  const ctx = runner.createContext();
  const flush = async () => {
    await Promise.all(routingPromises);
    assert.deepEqual(routingErrors, [], "installed message routing completed without error");
  };
  const emit = async (type, data = {}) => {
    await runner.emit({ type, ...data });
    assert.deepEqual(errors, [], "native extension lifecycle dispatch has no errors");
  };
  const tool = (name, args, signal) => extension.tools.get(name).definition.execute("live", args, signal, undefined, ctx);
  const connection = (action, extra = {}) => tool("nodalwire_connection", { action, ...extra });
  const network = (action, network, extra = {}) => tool("nodalwire_network", { action, network, ...extra });
  const send = (to, content, extra = {}, signal) => tool("nodalwire_send", { to, message: message(content), ...extra }, signal);
  const request = (to, content, extra = {}, signal) => tool("nodalwire_request", { to, message: message(content), ...extra }, signal);
  const reply = (replyRef, content, extra = {}, signal) => tool("nodalwire_reply", { replyRef, message: message(content), ...extra }, signal);
  const consume = message => emit("message_end", { message: { role: "custom", ...message } });
  const incoming = async (id, consumeTicket = true) => {
    await waitFor(() => received.some(item => item.message.details.id === id));
    await flush();
    const item = received.find(item => item.message.details.id === id);
    if (consumeTicket) await consume(item.message);
    return item;
  };
  const deliver = async (node, content, { options, transport = {}, consumeTicket = true } = {}) => {
    const id = await node.send("pi-live", encodeMessage(message(content), options), transport);
    return incoming(id, consumeTicket);
  };
  try {
    await emit("session_start", { reason: "startup" }); // No name flag: no auto-connect.
    assert.equal((await connection("status")).details.status, "disconnected");
    await run({ loaded, notices, received, routed, fake, flush, emit, tool, connection, network, send, request, reply, consume, incoming, deliver });
  } finally {
    await emit("session_shutdown", { reason: "quit" });
    await emit("session_shutdown", { reason: "quit" });
    await flush();
    assert.equal((await connection("status")).details.status, "disconnected");
  }
}

// All clients are scoped to this one invocation. Subtests run sequentially.
test("published v0.3.0 transport and Pi integration (no model)", async t => {
  const clients = [];
  const connect = async (name, address = endpoint) => {
    const node = await Node.connect(name, address);
    clients.push(node);
    return node;
  };
  try {
    const alice = await connect("sdk-node");
    const bob = await connect("sdk-peer");
    const blocked = await connect("blocked-peer");

    await t.test("opaque Node↔Python and Node↔Node default exchanges and native IDs", async () => {
      const payload = Uint8Array.of(0, 255, 42);
      const pythonId = await alice.send("python-peer", payload);
      const python = await receive(alice);
      assert.equal(python.sender, "python-peer");
      assert.equal(python.network, "default");
      assert.equal(python.reply_to, pythonId);
      assert.deepEqual([...python.payload], [...payload]);
      const acceptedId = await alice.send("sdk-peer", payload);
      assert.match(acceptedId, ID);
      const incoming = await receive(bob);
      assert.equal(incoming.id, acceptedId);
      assert.equal(incoming.reply_to, undefined);
      assert.equal(incoming.sender, "sdk-node");
      assert.equal(incoming.network, "default");
      assert.deepEqual([...incoming.payload], [...payload]);
      const replyId = await bob.reply(incoming, payload);
      const returned = await receive(alice);
      assert.equal(returned.id, replyId);
      assert.notEqual(replyId, acceptedId);
      assert.equal(returned.reply_to, acceptedId);
      assert.deepEqual([...returned.payload], [...payload]);
      const legacy = Buffer.from("NWR1\0opaque");
      await alice.send("sdk-peer", legacy);
      assert.deepEqual(Buffer.from((await receive(bob)).payload), legacy, "transport never unwraps application bytes");
      const crossLanguage = await alice.request("python-peer", payload, { timeout: 1 });
      assert.equal(crossLanguage.sender, "python-peer");
      assert.match(crossLanguage.reply_to, ID);
      assert.deepEqual([...crossLanguage.payload], [...payload]);
    });

    await t.test("admission, global name namespace, directional routing and missing destination", async () => {
      await rejectsCode(Node.connect("forbidden-peer", endpoint), "admission_denied");
      await rejectsCode(Node.connect("sdk-node", endpoint), "duplicate_name");
      await rejectsCode(alice.send("missing-peer", Uint8Array.of(1)), "destination_unavailable");
      await rejectsCode(alice.send("blocked-peer", Uint8Array.of(1)), "route_denied");
      await blocked.send("sdk-node", Uint8Array.of(2));
      assert.deepEqual([...(await receive(alice)).payload], [2]);
    });

    await t.test("published open/protected memberships, isolation, idempotence and leave", async () => {
      await rejectsCode(alice.send("sdk-peer", Uint8Array.of(1), { network: "team" }), "not_member");
      assert.deepEqual(await alice.join("team"), { network: "team", joined: true, changed: true });
      assert.deepEqual(await alice.join("team"), { network: "team", joined: true, changed: false });
      await rejectsCode(Node.connect("sdk-node", endpoint), "duplicate_name");
      await rejectsCode(alice.send("sdk-peer", Uint8Array.of(1), { network: "team" }), "destination_not_member");
      await bob.join("team");
      await alice.send("sdk-peer", Uint8Array.of(3), { network: "team" });
      assert.equal((await receive(bob)).network, "team");
      await rejectsCode(alice.send("sdk-peer", Uint8Array.of(1), { network: "other" }), "not_member");
      await rejectsCode(alice.join("protected"), "join_denied");
      await rejectsCode(alice.join("protected", "incorrect"), "join_denied");
      await alice.join("protected", credential);
      await bob.join("protected", credential);
      await alice.send("sdk-peer", Uint8Array.of(4), { network: "protected" });
      assert.equal((await receive(bob)).network, "protected");
      assert.deepEqual(await alice.leave("protected"), { network: "protected", joined: false, changed: true });
      assert.deepEqual(await alice.leave("protected"), { network: "protected", joined: false, changed: false });
      await rejectsCode(alice.send("sdk-peer", Uint8Array.of(1), { network: "protected" }), "not_member");
      await rejectsCode(alice.join("missing"), "network_not_found");
      await bob.leave("protected");
      await bob.leave("team");
    });

    await t.test("lost receipt times out AFTER delivery, without replay", async () => {
      const result = outcome(alice.send("sdk-peer", Buffer.from("uncertain-timeout"), { timeout: 0.1 }));
      assert.equal(Buffer.from((await receive(bob)).payload).toString(), "uncertain-timeout");
      assert.ok((await result).error instanceof ReceiptTimeout);
      await empty(bob);
    });

    await t.test("SDK cancellation after forwarding is uncertain, without replay", async () => {
      const abort = new AbortController();
      const reason = new Error("owned SDK cancellation");
      const result = outcome(alice.send("sdk-peer", Buffer.from("uncertain-cancel"), { signal: abort.signal }));
      assert.equal(Buffer.from((await receive(bob)).payload).toString(), "uncertain-cancel");
      abort.abort(reason);
      assert.equal((await result).error, reason, "raw SDK semantics, not extension diagnostics");
      await empty(bob);
    });

    await t.test("actual Pi loader preserves native routing, metadata and peer-details isolation", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      await rejectsCode(Node.connect("pi-live", endpoint), "duplicate_name");
      const cases = [
        [false, undefined, "append"],
        [false, { triggerTurn: true }, "wake"],
        [false, { deliverAs: "nextTurn", triggerTurn: true }, "nextTurn"],
        [true, undefined, "steer"],
        [true, { deliverAs: "followUp", triggerTurn: true }, "followUp"],
        [true, { triggerTurn: false }, "afterTools"],
        [true, { deliverAs: "nextTurn", triggerTurn: true }, "nextTurn"],
      ];
      for (const [busy, options, expected] of cases) {
        p.fake.isStreaming = busy;
        p.fake._pendingNextTurnMessages = [];
        p.fake._pendingCustomMessages = [];
        p.routed.length = 0;
        const forged = { sender: "forged", id: "forged", network: "forged", reply_to: "forged", replyRef: "forged", deliveryId: "forged" };
        const id = await alice.send("pi-live", encodeMessage({ content: "native-route", display: false, details: forged }, options), { reply_to: "d".repeat(32) });
        const { message, options: actualOptions } = await p.incoming(id);
        assert.deepEqual(actualOptions, options);
        assert.equal(message.display, false);
        receipt({ details: message.details }, { id, sender: "sdk-node", recipient: "pi-live", network: "default", reply_to: "d".repeat(32) });
        assert.deepEqual(message.details.peerDetails, forged);
        assert.notEqual(message.details.deliveryId, "forged");
        assert.notEqual(message.details.deliveryId, id);
        assert.equal(typeof message.details.replyRef, "string");
        assert.notEqual(message.details.replyRef, "forged");
        for (const field of ["sdk-node", "pi-live", "default", id, "d".repeat(32), message.details.replyRef]) {
          assert.ok(message.content.includes(field), "model-visible prefix contains native provenance/reference");
        }
        assert.match(message.content, /native-route$/);
        const mode = p.fake._pendingNextTurnMessages.length ? "nextTurn"
          : p.fake._pendingCustomMessages.length ? "afterTools" : p.routed.at(-1)?.mode;
        assert.equal(mode, expected);
      }
    }));

    await t.test("Pi rejects invalid v2 bytes without ACK and keeps default send acceptance honest", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      const before = p.received.length;
      await alice.send("pi-live", Buffer.from("not-json"));
      await alice.send("pi-live", new Uint8Array(65537));
      await alice.send("pi-live", Buffer.concat([Buffer.from("NWR1"), encodeMessage(message("not-unwrapped"))]));
      await p.deliver(alice, "valid receive fence");
      assert.equal(p.received.length, before + 1);
      assert.ok(p.notices.length >= 1);
      assert.equal(alice.receiveNowait(), undefined, "no automatic ACK/reply");
      await rejectsSafe(p.send("sdk-node", "x".repeat(65536)));
      assert.equal(alice.receiveNowait(), undefined);
      const sent = await p.send("sdk-peer", "pi-outbound");
      receipt(sent, { status: "relay_accepted", to: "sdk-peer", network: "default" });
      assert.match(sent.details.id, ID);
      assert.match(sent.content.map(block => block.text ?? "").join(""), /not confirmed/i);
      const outgoing = await receive(bob);
      assert.equal(outgoing.id, sent.details.id);
      assert.equal(outgoing.sender, "pi-live");
      assert.equal(outgoing.network, "default");
      assert.deepEqual(decodeMessage(outgoing.payload), { version: 2, message: message("pi-outbound") });
      await rejectsSafe(p.send("missing-peer", "missing"), /destination_unavailable/);
    }));

    await t.test("Pi open/protected joins use bound aliases, preserve isolation and invalidate refs on leave", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      await rejectsSafe(p.send("sdk-peer", "not joined", { network: "team" }), /not_member/);
      receipt(await p.network("join", "team"), { network: "team", joined: true, changed: true });
      receipt(await p.network("join", "team"), { network: "team", joined: true, changed: false });
      await rejectsSafe(p.send("sdk-peer", "peer not joined", { network: "team" }), /destination_not_member/);
      await bob.join("team");
      const sent = await p.send("sdk-peer", "named network", { network: "team", options: { triggerTurn: false } });
      const packet = await receive(bob);
      assert.equal(packet.id, sent.details.id);
      assert.equal(packet.network, "team");
      assert.deepEqual(decodeMessage(packet.payload).options, { triggerTurn: false });
      await rejectsSafe(p.send("sdk-peer", "no network fallback", { network: "other" }), /not_member/);
      await empty(bob);
      await rejectsSafe(p.network("join", "protected"), /join_denied/);
      await rejectsSafe(p.network("join", "protected", { credentialRef: "wrong-primary" }), /join_denied/);
      await rejectsSafe(p.network("join", "team", { credentialRef: "protected-primary" }));
      await rejectsSafe(p.network("join", "protected", { credentialRef: "protected-default" }));
      await rejectsSafe(p.network("join", "team", { credential: "RAW-CREDENTIAL-MUST-NOT-BE-ACCEPTED" }));
      await rejectsSafe(p.network("leave", "team", { credentialRef: "protected-primary" }));
      receipt(await p.network("join", "protected", { credentialRef: "protected-primary" }), { network: "protected", joined: true, changed: true });
      await bob.join("protected", credential);
      const received = await p.deliver(bob, "Please reply on protected", { transport: { network: "protected" } });
      assert.equal(received.message.details.network, "protected");
      assert.equal(typeof received.message.details.replyRef, "string");
      receipt(await p.network("leave", "protected"), { network: "protected", joined: false, changed: true });
      await rejectsSafe(p.reply(received.message.details.replyRef, "stale ref after leave"));
      await rejectsSafe(p.send("sdk-peer", "removed membership", { network: "protected" }), /not_member/);
      await empty(bob);
      await p.send("sdk-peer", "default still available");
      assert.equal((await receive(bob)).network, "default");
      await bob.leave("team");
      await bob.leave("protected");
    }));

    await t.test("protected default admits Pi but requires correct explicit membership; reconnect forgets joins", async () => {
      const peer = await connect("protected-b", protectedEndpoint);
      await withPi(async p => {
        await p.connection("connect", { name: "pi-live", endpoint: protectedEndpoint });
        await rejectsSafe(p.send("protected-b", "admitted is not joined"), /not_member/);
        await rejectsSafe(p.network("join", "default"), /join_denied/);
        await rejectsSafe(p.network("join", "default", { credentialRef: "wrong-default" }), /join_denied/);
        await p.network("join", "default", { credentialRef: "protected-default" });
        await rejectsSafe(p.send("protected-b", "recipient not joined"), /destination_not_member/);
        await peer.join("default", credential);
        await p.send("protected-b", "authorized default");
        assert.equal((await receive(peer)).network, "default");
        await p.connection("disconnect");
        await p.connection("connect", { name: "pi-live", endpoint: protectedEndpoint });
        await rejectsSafe(p.send("protected-b", "no retained membership"), /not_member/);
        await empty(peer);
      });
      await peer.close();
    });

    await t.test("Pi reply references preserve the original route/options and are single-use", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      await p.network("join", "team");
      await bob.join("team");
      const received = await p.deliver(bob, "Please reply using this reference", { transport: { network: "team" } });
      const { replyRef, id } = received.message.details;
      assert.equal(typeof replyRef, "string");
      // Invalid content, overrides and pre-abort must not consume the reference.
      await rejectsSafe(p.reply(replyRef, "x".repeat(65536)));
      await rejectsSafe(p.reply(replyRef, "override", { network: "default" }));
      await rejectsSafe(p.reply(replyRef, "override", { to: "sdk-node" }));
      const stopped = new AbortController();
      stopped.abort(new Error("PRIVATE-ABORT-REASON"));
      await rejectsSafe(p.reply(replyRef, "pre-aborted", {}, stopped.signal));
      const options = { deliverAs: "nextTurn", triggerTurn: true };
      const result = await p.reply(replyRef, "native reply", { options });
      const incoming = await receive(bob);
      assert.equal(incoming.id, result.details.id);
      assert.notEqual(incoming.id, id);
      assert.equal(incoming.reply_to, id);
      assert.equal(incoming.network, "team");
      assert.equal(incoming.sender, "pi-live");
      assert.deepEqual(decodeMessage(incoming.payload), { version: 2, message: message("native reply"), options });
      await rejectsSafe(p.reply(replyRef, "do not duplicate"));
      await empty(bob);
      await bob.leave("team");
    }));

    await t.test("Pi request matches native sender/network/correlation while ordinary receives continue", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      await p.network("join", "team");
      await bob.join("team");
      const options = { deliverAs: "followUp", triggerTurn: true };
      let settled = false;
      const result = outcome(p.request("sdk-peer", "Please reply to this named request", { network: "team", options, timeoutSeconds: 3 }));
      void result.then(() => { settled = true; });
      const request = await receive(bob);
      assert.equal(request.network, "team");
      assert.deepEqual(decodeMessage(request.payload).options, options);
      const before = p.received.length;
      const forgedDetails = { id: "forged", sender: "forged", network: "forged", reply_to: "forged" };
      // A real third peer may set correlation metadata, but cannot match the expected sender.
      const wrongSender = await alice.send("pi-live", encodeMessage({ ...message("wrong sender"), details: forgedDetails }), { network: "default", reply_to: request.id });
      const wrongNetwork = await bob.send("pi-live", encodeMessage(message("wrong network")), { network: "default", reply_to: request.id });
      const wrongId = await bob.send("pi-live", encodeMessage(message("wrong correlation")), { network: "team", reply_to: "e".repeat(32) });
      // To isolate sender matching too, use a third peer on the correct network.
      await alice.join("team");
      const sameNetworkWrongSender = await alice.send("pi-live", encodeMessage(message("same network wrong sender")), { network: "team", reply_to: request.id });
      for (const id of [wrongSender, wrongNetwork, wrongId, sameNetworkWrongSender]) await p.incoming(id);
      p.fake.isStreaming = true;
      await p.deliver(alice, "ordinary follow-up", { options: { deliverAs: "followUp", triggerTurn: true } });
      await p.deliver(alice, "ordinary steering", { options: { deliverAs: "steer", triggerTurn: true } });
      assert.deepEqual(p.routed.slice(-2).map(item => item.mode), ["followUp", "steer"]);
      assert.equal(settled, false, "forged/wrong replies do not settle the request");
      const replyOptions = { triggerTurn: false };
      const replyId = await bob.reply(request, encodeMessage({ content: "matched answer", display: false, details: forgedDetails }, replyOptions));
      const answer = await result;
      assert.ok(!answer.error, "matching reply resolves request");
      receipt(answer.value, { id: replyId, sender: "sdk-peer", network: "team", reply_to: request.id });
      assert.equal(p.received.length, before + 6, "matched answer is not duplicated into ordinary Pi receive");
      const text = answer.value.content.filter(block => block.type === "text").map(block => block.text).join("\n");
      assert.ok(text.includes("matched answer"));
      for (const field of [replyId, "sdk-peer", "team", request.id]) assert.ok(text.includes(field));
      const duplicate = await bob.reply(request, encodeMessage(message("duplicate reply becomes ordinary")));
      await p.incoming(duplicate);
      assert.equal(p.received.length, before + 7);
      await bob.leave("team");
    }));

    await t.test("request success on protected network and bounded result content", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      await p.network("join", "protected", { credentialRef: "protected-primary" });
      await bob.join("protected", credential);
      const result = outcome(p.request("sdk-peer", "Please reply on protected", { network: "protected", timeoutSeconds: 3 }));
      const request = await receive(bob);
      assert.equal(request.network, "protected");
      // Exactly legal field-limit content must remain intact without combining
      // the provenance prefix into an oversized text field or serializing v2 JSON.
      const content = "x".repeat(48 * 1024);
      const id = await bob.reply(request, encodeMessage(message(content)));
      const answer = await result;
      assert.ok(!answer.error);
      assert.equal(answer.value.details.id, id);
      for (const block of answer.value.content) if (block.type === "text") {
        assert.ok(Buffer.byteLength(block.text) <= 48 * 1024, "tool content remains bounded");
      }
      assert.ok(answer.value.content.some(block => block.type === "text" && block.text.includes(content)));
      assert.equal(p.received.length, 0);
      await bob.leave("protected");
    }));

    await t.test("invalid matched application reply fails safely without ordinary replay", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      const result = outcome(p.request("sdk-peer", "Please reply with valid v2", { timeoutSeconds: 3 }));
      const request = await receive(bob);
      await bob.reply(request, Buffer.from("PRIVATE-invalid-v2-reply"));
      const failed = await result;
      safeError(failed.error);
      assert.ok(!String(failed.error).includes("PRIVATE-invalid-v2-reply"));
      await p.deliver(bob, "post-invalid reply fence");
      assert.equal(p.received.length, 1, "invalid matched bytes never re-enter ordinary receive");
    }));

    await t.test("matching reply succeeds even when the owned relay drops the SEND receipt", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      const result = outcome(p.request("sdk-peer", "Please reply: missing request receipt", { timeoutSeconds: 2 }));
      const request = await receive(bob); // Real forwarding before receipt suppression.
      const id = await bob.reply(request, encodeMessage(message("answer without routing receipt")));
      const answer = await result;
      assert.ok(!answer.error);
      assert.equal(answer.value.details.id, id);
      assert.equal(answer.value.details.reply_to, request.id);
      assert.equal(p.received.length, 0);
      await empty(bob);
    }));

    await t.test("request timeout is uncertain, no retry, and late reply becomes ordinary", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      const result = outcome(p.request("sdk-peer", "Please reply after my deadline", { timeoutSeconds: 1 }));
      const request = await receive(bob); // Proven effect despite subsequent timeout.
      const failed = await result;
      safeError(failed.error, /uncertain|may have|not confirmed/i);
      await empty(bob);
      const late = await bob.reply(request, encodeMessage(message("late valid reply")));
      const ordinary = await p.incoming(late);
      assert.equal(ordinary.message.details.reply_to, request.id);
      assert.equal(p.received.length, 1);
      // A new waiter cannot be completed by the old correlation ID.
      const next = outcome(p.request("sdk-peer", "Please reply to a new request", { timeoutSeconds: 2 }));
      const nextRequest = await receive(bob);
      assert.notEqual(nextRequest.id, request.id);
      const anotherLate = await bob.reply(request, encodeMessage(message("another old reply")));
      await p.incoming(anotherLate);
      const right = await bob.reply(nextRequest, encodeMessage(message("new matching reply")));
      assert.equal((await next).value.details.id, right);
    }));

    await t.test("extension send/request cancellation sanitizes reasons and never retries", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      const stopped = new AbortController();
      stopped.abort(new Error("PRIVATE-ABORT-REASON"));
      await rejectsSafe(p.request("sdk-peer", "must not be sent", {}, stopped.signal));
      await empty(bob);
      for (const kind of ["send", "request"]) {
        const abort = new AbortController();
        const result = outcome(kind === "send"
          ? p.send("sdk-peer", "uncertain-extension", {}, abort.signal)
          : p.request("sdk-peer", "Please reply after cancellation", { timeoutSeconds: 3 }, abort.signal));
        const incoming = await receive(bob);
        abort.abort(new Error("PRIVATE-ABORT-REASON"));
        safeError((await result).error, /uncertain|may have|not confirmed/i);
        await empty(bob);
        if (kind === "request") {
          const late = await bob.reply(incoming, encodeMessage(message("late after cancellation")));
          await p.incoming(late);
        }
      }
    }));

    await t.test("uncertain reply consumes its reference once, without retry", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      const received = await p.deliver(bob, "Please reply once, even if receipt is lost");
      const abort = new AbortController();
      const result = outcome(p.reply(received.message.details.replyRef, "uncertain-reply", {}, abort.signal));
      const incoming = await receive(bob); // Forwarded despite intentionally missing receipt.
      assert.equal(incoming.reply_to, received.message.details.id);
      assert.equal(decodeMessage(incoming.payload).message.content, "uncertain-reply");
      abort.abort(new Error("PRIVATE-ABORT-REASON"));
      safeError((await result).error, /uncertain|may have|not confirmed/i);
      await rejectsSafe(p.reply(received.message.details.replyRef, "never restore an uncertain reference"));
      await empty(bob);
    }));

    await t.test("four concurrent Pi requests match independently; capacity releases after settlement", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      const pending = [], incoming = [];
      const abort = new AbortController();
      try {
        // Await each peer observation, avoiding the SDK's separate no-backlog native
        // writer limit while deliberately leaving four application waiters active.
        for (let n = 0; n < 4; n++) {
          pending.push(outcome(p.request("sdk-peer", `Please reply to concurrent request ${n}`, { timeoutSeconds: 3 }, abort.signal)));
          incoming.push(await receive(bob));
        }
        await rejectsSafe(p.request("sdk-peer", "must not exceed capacity", { timeoutSeconds: 3 }));
        await empty(bob);
        for (const request of [...incoming].reverse()) {
          await bob.reply(request, encodeMessage(message(`answer for ${request.id}`)));
        }
        const results = await Promise.all(pending);
        for (let n = 0; n < results.length; n++) {
          assert.ok(!results[n].error);
          assert.equal(results[n].value.details.reply_to, incoming[n].id);
        }
        assert.equal(p.received.length, 0);
        const next = outcome(p.request("sdk-peer", "Please reply after capacity release", { timeoutSeconds: 2 }));
        const request = await receive(bob);
        const id = await bob.reply(request, encodeMessage(message("capacity available")));
        assert.equal((await next).value.details.id, id);
      } finally {
        abort.abort();
        await Promise.all(pending);
      }
    }));

    await t.test("32 Pi tickets remain bounded across reconnect and consumption releases capacity", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      for (let n = 0; n < 33; n++) {
        await bob.send("pi-live", encodeMessage(message(`deferred-${n}`), { deliverAs: "nextTurn" }));
      }
      // Relay acceptance is not Pi admission. Wait for an observed drop warning
      // as well as the 32 admissions; no fabricated message_end releases tickets.
      await waitFor(() => p.received.length === 32 && p.notices.length > 0);
      await p.flush();
      await p.connection("disconnect");
      await p.connection("connect", { name: "pi-live", endpoint });
      await bob.send("pi-live", encodeMessage(message("still full")));
      // A correlated round-trip is a receive-progress fence that needs no Pi
      // ticket. It also checks that ordinary capacity does not block requests.
      const fence = outcome(p.request("sdk-peer", "Please reply to the capacity fence", { timeoutSeconds: 2 }));
      const fenceRequest = await receive(bob);
      await bob.reply(fenceRequest, encodeMessage(message("capacity fence reply")));
      assert.ok(!(await fence).error);
      assert.equal(p.received.length, 32, "reconnect did not admit an extra ordinary packet");
      await p.consume(p.received[0].message);
      const released = await bob.send("pi-live", encodeMessage(message("capacity released")));
      await p.incoming(released);
      assert.equal(p.received.length, 33, "reconnect did not clear tickets");
    }));

    await t.test("disconnect cancels requests, invalidates reply refs and releases the owned name", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      const received = await p.deliver(bob, "Please reply before disconnect");
      const pending = outcome(p.request("sdk-peer", "Please reply before shutdown", { timeoutSeconds: 3 }));
      const old = await receive(bob);
      await p.connection("disconnect");
      safeError((await pending).error, /uncertain|may have|not confirmed/i);
      const released = await connect("pi-live"); // Proves real relay release.
      await released.close();
      await p.connection("connect", { name: "pi-live", endpoint });
      await rejectsSafe(p.reply(received.message.details.replyRef, "stale connection reference"));
      const late = await bob.reply(old, encodeMessage(message("old request after reconnect")));
      await p.incoming(late);
      const current = outcome(p.request("sdk-peer", "Please reply on current connection", { timeoutSeconds: 2 }));
      const request = await receive(bob);
      const id = await bob.reply(request, encodeMessage(message("current reply")));
      assert.equal((await current).value.details.id, id);
      const shuttingDown = outcome(p.request("sdk-peer", "Please reply before final shutdown", { timeoutSeconds: 3 }));
      await receive(bob);
      await p.emit("session_shutdown", { reason: "quit" });
      safeError((await shuttingDown).error, /uncertain|may have|not confirmed/i);
    }));

    await t.test("strict tool runtime rejects invalid timeout/network/routing controls before send", () => withPi(async p => {
      await p.connection("connect", { name: "pi-live", endpoint });
      for (const timeoutSeconds of [0, -1, 1.5, 121, "1", NaN, Infinity]) {
        await rejectsSafe(p.request("sdk-peer", "invalid deadline", { timeoutSeconds }));
      }
      for (const network of ["", "bad/name", "with space", 1]) {
        await rejectsSafe(p.send("sdk-peer", "invalid network", { network }));
        await rejectsSafe(p.request("sdk-peer", "invalid network", { network }));
      }
      await rejectsSafe(p.request("sdk-peer", "no raw IDs", { reply_to: "f".repeat(32), timeoutSeconds: 1 }));
      await rejectsSafe(p.tool("nodalwire_network", { action: "status", network: "team" }));
      await empty(bob);
    }));
  } finally {
    const results = await Promise.allSettled(clients.map(node => node.close({ timeout: 1 })));
    assert.ok(results.every(result => result.status === "fulfilled"), "all owned SDK clients closed cleanly");
  }
});
