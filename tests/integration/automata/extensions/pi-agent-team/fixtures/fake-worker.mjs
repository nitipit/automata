// Offline Pi RPC protocol double. Never imports a model/provider or touches sessions.
import { createInterface } from "node:readline";
const args = process.argv.slice(2);
const arg = name => args.includes(name) ? args[args.indexOf(name) + 1] : undefined;
const scenario = process.env.AGENT_FAKE_SCENARIO;
let timer, active = false;
const sessionId = arg("--session") || `fake-${process.pid}`;
const out = packet => process.stdout.write(JSON.stringify(packet) + "\n");
const response = (command, data, success = true) => out({ type: "response", id: command.id, command: command.type, success, data, ...(!success ? { error: "Rejected for test" } : {}) });
const finish = (text, aborted = false) => {
  active = false;
  out({ type: "message_end", message: { role: "assistant", content: [{ type: "text", text }], stopReason: text === "error" ? "error" : "stop", errorMessage: text === "error" ? "Provider failed" : undefined } });
  out({ type: "agent_end", messages: [], willRetry: false });
  timer = setTimeout(() => {
    out({ type: "agent_settled", aborted });
    if (text === "duplicate") out({ type: "agent_settled", aborted });
  }, 30);
};
const input = createInterface({ input: process.stdin });
input.on("line", line => {
  const command = JSON.parse(line);
  if (command.type === "get_state") {
    if (scenario === "startup-failure" || scenario === "startup-diagnostic") {
      const diagnostic = scenario === "startup-diagnostic" ? "สวัสดี".repeat(2000) + "\nfinal diagnostic\n"
        : `No session found matching '${arg("--session")}'\n`;
      process.stderr.write(diagnostic, () => process.exit(1));
      return;
    }
    if (scenario === "startup-silent") return process.exit(2);
    const reply = () => response(command, { launchArgs: args, model: { provider: arg("--provider"), id: scenario === "mismatch" ? "wrong" : arg("--model") }, thinkingLevel: arg("--thinking"), sessionId: scenario === "resume-mismatch" ? "different-session" : sessionId,
      sessionFile: `/fake/${sessionId}.jsonl`, isStreaming: active, isCompacting: false, pendingMessageCount: 0 });
    if (scenario === "delayed-state") setTimeout(reply, 80); else reply();
  } else if (command.type === "prompt") {
    const text = command.message;
    if (text === "reject") return response(command, undefined, false);
    if (text === "handled") return response(command, { disposition: "handled" });
    if (text === "late-reject") return setTimeout(() => response(command, undefined, false), 100);
    active = true;
    if (text !== "lost") {
      if (text === "late") setTimeout(() => response(command, { disposition: "started" }), 100);
      else response(command, { disposition: "started" });
    }
    out({ type: "agent_start" });
    if (text === "crash") return setTimeout(() => process.exit(2), 10);
    if (text === "lost" || text === "late") return;
    if (text === "malformed") { process.stdout.write("not-json-secret\n"); process.stderr.write("diagnostic สวัสดี\n"); }
    if (text === "oversize") process.stdout.write("x".repeat(2048) + "\n");
    if (text === "dialog") out({ type: "extension_ui_request", id: "dialog-1", method: "confirm", title: "Permission?" });
    if (text === "chunks") {
      const line = Buffer.from(JSON.stringify({ type: "message_update", delta: "สวัสดี\u2028still-one-record\u2029" }) + "\r\n");
      process.stdout.write(line.subarray(0, 10));
      process.stdout.write(line.subarray(10, 51));
      process.stdout.write(line.subarray(51));
    }
    timer = setTimeout(() => finish(text), text === "slow" ? 500 : 10);
  } else if (command.type === "steer") {
    response(command, { disposition: "queued" });
  } else if (command.type === "follow_up") {
    out({ type: "queue_update", steering: [], followUp: [command.message] });
    response(command, { disposition: "queued" });
  } else if (command.type === "abort") {
    clearTimeout(timer);
    finish("aborted", true);
    response(command);
  } else if (command.type === "extension_ui_response") {
    out({ type: "dialog_response_observed", cancelled: command.cancelled, confirmed: command.confirmed });
  }
});
input.on("close", () => {
  if (scenario !== "stubborn") process.exit(0);
});
if (scenario === "stubborn") {
  setInterval(() => {}, 1000);
  process.on("SIGTERM", () => {});
}
