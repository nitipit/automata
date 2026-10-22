import assert from "node:assert/strict";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const { encodeMessage, decodeMessage } =
  await import(pathToFileURL(join(process.env.PI_EXTENSION_TEST_ROOT, "protocol.ts")));
const message = { content: "Hello", display: true };

test("mapped combinations agree with installed Pi sendCustomMessage implementation", async () => {
  // Execute the installed API method with inert collaborators: no agent process,
  // network, model request or full-runtime timing claim.
  const { AgentSession } = await import(pathToFileURL(join(process.env.PI_TEST_PACKAGE_ROOT, "dist/index.js")));
  for (const busy of [false, true]) {
    for (const deliverAs of [undefined, "steer", "followUp", "nextTurn"]) {
      for (const triggerTurn of [undefined, false, true]) {
        const observed = [];
        const fake = {
          isStreaming: busy, _isEmittingAgentSettled: false,
          _pendingNextTurnMessages: [], _pendingCustomMessages: [],
          agent: { steer: () => observed.push("steer"), followUp: () => observed.push("followUp") },
          _appendCustomMessage: () => observed.push("append"),
          _startRun: async () => observed.push("start"),
        };
        const options = {};
        if (deliverAs !== undefined) options.deliverAs = deliverAs;
        if (triggerTurn !== undefined) options.triggerTurn = triggerTurn;
        const packet = decodeMessage(encodeMessage(message, options));
        await AgentSession.prototype.sendCustomMessage.call(fake, { customType: "probe", ...message }, packet.options);
        const actual = fake._pendingNextTurnMessages.length ? "nextTurn"
          : fake._pendingCustomMessages.length ? "afterTools" : observed[0];
        const expected = deliverAs === "nextTurn" ? "nextTurn"
          : busy && triggerTurn !== false ? (deliverAs === "followUp" ? "followUp" : "steer")
          : triggerTurn ? "start" : busy ? "afterTools" : "append";
        assert.equal(actual, expected, JSON.stringify({ busy, options }));
      }
    }
  }
});
