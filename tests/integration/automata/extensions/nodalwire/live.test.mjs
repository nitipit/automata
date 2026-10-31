// Opt-in: installed published SDK/relay, actual Pi loader + native message routing.
// No provider is constructed. Agent run/queue collaborators below are intentionally inert.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { findPackageJSON } from "node:module";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const root = process.env.PI_EXTENSION_TEST_ROOT;
const piRoot = process.env.PI_TEST_PACKAGE_ROOT;
const clientManifest = findPackageJSON("@devcapsule/nodalwire-client", pathToFileURL(join(root, "package.json")));
const { Node, ReceiptTimeout } = await import(pathToFileURL(join(dirname(clientManifest), "dist/index.js")));
const { loadExtensions } = await import(pathToFileURL(join(piRoot, "dist/core/extensions/loader.js")));
const { AgentSession, SessionManager } = await import(pathToFileURL(join(piRoot, "dist/index.js")));
const { ExtensionRunner } = await import(pathToFileURL(join(piRoot, "dist/core/extensions/runner.js")));
const { encodeMessage } = await import(pathToFileURL(join(root, "protocol.ts")));
const endpoint = process.env.NODALWIRE_TRIAL_ENDPOINT;
const protectedEndpoint = process.env.NODALWIRE_TRIAL_PROTECTED_ENDPOINT;
const credential = process.env.NODALWIRE_TRIAL_JOIN_TOKEN;
const receive = node => node.receive({ signal: AbortSignal.timeout(3000) });
const rejectsCode = (promise, code) => assert.rejects(promise, error => error.code === code);
const waitFor = async predicate => {
  const deadline = performance.now() + 3000;
  while (!predicate()) {
    assert.ok(performance.now() < deadline, "bounded wait expired");
    await new Promise(resolve => setTimeout(resolve, 5));
  }
};

assert.equal(JSON.parse(await readFile(clientManifest, "utf8")).version, "0.3.0");

test("published v0.3.0 transport and Pi integration (no model)", async t => {
  const clients = [];
  const connect = async (name, address = endpoint) => {
    const node = await Node.connect(name, address);
    clients.push(node);
    return node;
  };
  let emit;
  try {
    const alice = await connect("sdk-node");
    const bob = await connect("sdk-peer");
    const blocked = await connect("blocked-peer");

    await t.test("opaque Node↔Python and Node↔Node default exchanges", async () => {
      const payload = Uint8Array.of(0, 255, 42);
      await alice.send("python-peer", payload);
      const python = await receive(alice);
      assert.equal(python.sender, "python-peer");
      assert.equal(python.network, "default");
      assert.deepEqual([...python.payload], [...payload]);
      const acceptedId = await alice.send("sdk-peer", payload);
      assert.match(acceptedId, /^[a-f0-9]{32}$/);
      const incoming = await receive(bob);
      assert.equal(incoming.id, acceptedId);
      assert.equal(incoming.reply_to, undefined);
      assert.equal(incoming.sender, "sdk-node");
      assert.equal(incoming.network, "default");
      assert.deepEqual([...incoming.payload], [...payload]);
      const replyId = await bob.send(incoming.sender, incoming.payload, { reply_to: incoming.id });
      const returned = await receive(alice);
      assert.equal(returned.id, replyId);
      assert.notEqual(replyId, acceptedId);
      assert.equal(returned.reply_to, acceptedId);
      assert.deepEqual([...returned.payload], [...payload]);
      // NWM3 never interprets NWR1-looking application bytes.
      const legacy = Buffer.from("NWR1\\0opaque");
      await alice.send("sdk-peer", legacy);
      assert.deepEqual(Buffer.from((await receive(bob)).payload), legacy);
    });

    await t.test("admission, duplicate name, directional routing and missing destination", async () => {
      await rejectsCode(Node.connect("forbidden-peer", endpoint), "admission_denied");
      await rejectsCode(Node.connect("sdk-node", endpoint), "duplicate_name");
      await rejectsCode(alice.send("missing-peer", Uint8Array.of(1)), "destination_unavailable");
      await rejectsCode(alice.send("blocked-peer", Uint8Array.of(1)), "route_denied");
      await blocked.send("sdk-node", Uint8Array.of(2));
      assert.deepEqual([...(await receive(alice)).payload], [2]);
    });

    await t.test("explicit open/protected memberships, denials and leave", async () => {
      await rejectsCode(alice.send("sdk-peer", Uint8Array.of(1), { network: "team" }), "not_member");
      assert.deepEqual(await alice.join("team"), { network: "team", joined: true, changed: true });
      await rejectsCode(alice.send("sdk-peer", Uint8Array.of(1), { network: "team" }), "destination_not_member");
      await bob.join("team");
      await alice.send("sdk-peer", Uint8Array.of(3), { network: "team" });
      assert.equal((await receive(bob)).network, "team");
      await rejectsCode(alice.join("protected"), "join_denied");
      await rejectsCode(alice.join("protected", "incorrect"), "join_denied");
      await alice.join("protected", credential);
      await bob.join("protected", credential);
      await alice.send("sdk-peer", Uint8Array.of(4), { network: "protected" });
      assert.equal((await receive(bob)).network, "protected");
      assert.deepEqual(await alice.leave("protected"), { network: "protected", joined: false, changed: true });
      await rejectsCode(alice.send("sdk-peer", Uint8Array.of(1), { network: "protected" }), "not_member");
      await rejectsCode(alice.join("missing"), "network_not_found");
    });

    await t.test("protected default admits registration but requires explicit authorized join", async () => {
      const a = await connect("protected-a", protectedEndpoint);
      const b = await connect("protected-b", protectedEndpoint);
      await rejectsCode(a.send("protected-b", Uint8Array.of(1)), "not_member");
      await rejectsCode(a.join("default", "incorrect"), "join_denied");
      await a.join("default", credential);
      await rejectsCode(a.send("protected-b", Uint8Array.of(1)), "destination_not_member");
      await b.join("default", credential);
      await a.send("protected-b", Uint8Array.of(5));
      assert.equal((await receive(b)).network, "default");
    });

    await t.test("lost receipt times out AFTER delivery, with no replay", async () => {
      // Owned relay fault injection suppresses only this SEND receipt after forwarding.
      const result = alice.send("sdk-peer", Buffer.from("uncertain-timeout"), { timeout: 0.1 })
        .then(() => undefined, error => error);
      assert.equal(Buffer.from((await receive(bob)).payload).toString(), "uncertain-timeout");
      assert.ok(await result instanceof ReceiptTimeout);
      await assert.rejects(bob.receive({ signal: AbortSignal.timeout(100) }), error => error.name === "TimeoutError");
    });

    await t.test("cancellation after forwarding is uncertain, with no replay", async () => {
      const abort = new AbortController();
      const reason = new Error("owned trial cancellation");
      const result = alice.send("sdk-peer", Buffer.from("uncertain-cancel"), { signal: abort.signal })
        .then(() => undefined, error => error);
      assert.equal(Buffer.from((await receive(bob)).payload).toString(), "uncertain-cancel");
      abort.abort(reason);
      assert.equal(await result, reason);
      await assert.rejects(bob.receive({ signal: AbortSignal.timeout(100) }), error => error.name === "TimeoutError");
    });

    await t.test("actual Pi loader/runtime path preserves native routing and provenance", async () => {
      const loaded = await loadExtensions([join(root, "index.ts")], root);
      assert.deepEqual(loaded.errors, []);
      assert.equal(loaded.extensions.length, 1);
      const extension = loaded.extensions[0];
      assert.deepEqual([...extension.tools.keys()].sort(), ["nodalwire_connection", "nodalwire_send"]);
      const notices = [], received = [], routed = [];
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
      // Real ExtensionAPI.sendMessage forwards through its loaded runtime to the
      // installed AgentSession method. Only the final run/queue collaborators are inert.
      loaded.runtime.sendMessage = (message, options) => {
        received.push({ message, options });
        void AgentSession.prototype.sendCustomMessage.call(fake, message, options);
      };
      const runner = new ExtensionRunner(loaded.extensions, loaded.runtime, root, SessionManager.inMemory(), {});
      runner.setUIContext({ notify: (...args) => notices.push(args), setStatus() {} });
      const errors = [];
      runner.onError(error => errors.push(error));
      const ctx = runner.createContext();
      emit = async (event, data = {}) => {
        await runner.emit({ type: event, ...data });
        assert.deepEqual(errors, [], "native extension lifecycle dispatch has no errors");
      };
      const tool = (name, args, signal) => extension.tools.get(name).definition.execute("live", args, signal, undefined, ctx);
      const connection = (action, extra = {}) => tool("nodalwire_connection", { action, ...extra });
      await emit("session_start"); // No flag: factory/startup stays disconnected.
      assert.equal((await connection("status")).details.status, "disconnected");
      assert.equal((await connection("connect", { name: "pi-live", endpoint })).details.status, "connected");
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
        fake.isStreaming = busy;
        fake._pendingNextTurnMessages = [];
        fake._pendingCustomMessages = [];
        routed.length = 0;
        const count = received.length;
        await alice.send("pi-live", encodeMessage({ content: "native-route", display: false, details: { sender: "forged" } }, options), { reply_to: "d".repeat(32) });
        await waitFor(() => received.length === count + 1);
        const { message, options: actualOptions } = received.at(-1);
        assert.deepEqual(actualOptions, options);
        assert.equal(message.display, false);
        assert.equal(message.details.sender, "sdk-node");
        assert.equal(message.details.recipient, "pi-live");
        assert.deepEqual(message.details.peerDetails, { sender: "forged" });
        assert.match(message.content, /^\[NodalWire: sdk-node → pi-live\]\n/);
        const mode = fake._pendingNextTurnMessages.length ? "nextTurn"
          : fake._pendingCustomMessages.length ? "afterTools" : routed.at(-1)?.mode;
        assert.equal(mode, expected);
        await emit("message_end", { message: { role: "custom", ...message } });
      }
      // Malformed/oversized packets are dropped locally; a following valid packet
      // fences reader progress. No ACK and no legacy request-envelope unwrapping.
      fake.isStreaming = false;
      const count = received.length;
      await alice.send("pi-live", Buffer.from("not-json"));
      await alice.send("pi-live", new Uint8Array(65537));
      await alice.send("pi-live", Buffer.concat([
        Buffer.from("NWR1"),
        encodeMessage({ content: "not-unwrapped", display: true }),
      ]));
      await alice.send("pi-live", encodeMessage({ content: "fence", display: true }));
      await waitFor(() => received.length === count + 1);
      assert.match(received.at(-1).message.content, /fence$/);
      assert.equal(notices.length, 1);
      assert.equal(alice.receiveNowait(), undefined, "receiving does not ACK");
      await assert.rejects(tool("nodalwire_send", { to: "sdk-node", message: { content: "x".repeat(65536), display: true } }));
      assert.equal(alice.receiveNowait(), undefined, "invalid outgoing packet was not sent");
      const sent = await tool("nodalwire_send", { to: "sdk-peer", message: { content: "pi-outbound", display: true } });
      assert.equal(sent.details.status, "relay_accepted");
      const outgoing = await receive(bob);
      assert.equal(outgoing.sender, "pi-live");
      assert.equal(outgoing.network, "default");
      assert.deepEqual(JSON.parse(Buffer.from(outgoing.payload)), { version: 2, message: { content: "pi-outbound", display: true } });
      await rejectsCode(tool("nodalwire_send", { to: "missing-peer", message: { content: "missing", display: true } }), "destination_unavailable");
      // Same real transport, now interrupt the extension send after a proven effect.
      const abort = new AbortController();
      const reason = new Error("owned extension cancellation");
      const result = tool("nodalwire_send", { to: "sdk-peer", message: { content: "uncertain-extension", display: true } }, abort.signal)
        .then(() => undefined, error => error);
      assert.equal(JSON.parse(Buffer.from((await receive(bob)).payload)).message.content, "uncertain-extension");
      abort.abort(reason);
      assert.equal(await result, reason);
      await assert.rejects(bob.receive({ signal: AbortSignal.timeout(100) }), error => error.name === "TimeoutError");
      await emit("session_shutdown");
      await emit("session_shutdown");
      assert.equal((await connection("status")).details.status, "disconnected");
      const released = await connect("pi-live"); // Confirms relay release, not merely local close.
      await released.close();
      // Pi intentionally has no join/credential API. Registration on a protected
      // default still succeeds, but its send remains denied without membership.
      assert.equal((await connection("connect", { name: "pi-live", endpoint: protectedEndpoint })).details.status, "connected");
      await rejectsCode(tool("nodalwire_send", { to: "protected-b", message: { content: "no-membership", display: true } }), "not_member");
      await connection("disconnect");
    });
  } finally {
    try {
      await emit?.("session_shutdown");
    } finally {
      const results = await Promise.allSettled(clients.map(node => node.close({ timeout: 1 })));
      assert.ok(results.every(result => result.status === "fulfilled"), "all owned SDK clients closed cleanly");
    }
  }
});
