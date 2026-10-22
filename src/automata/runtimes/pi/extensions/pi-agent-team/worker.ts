import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomUUID } from "node:crypto";
import { StringDecoder } from "node:string_decoder";
import { Capture, clip } from "./capture.ts";

export const WORKER_ENV = "AUTOMATA_AGENT_TEAM_WORKER";
export const TOOL_NAMES = ["agent_start", "agent_send", "agent_status", "agent_read", "agent_abort", "agent_stop"];
export const THINKING = ["off", "minimal", "low", "medium", "high", "xhigh", "max"] as const;
export type StartSpec = {
  workerId: string; cwd: string; provider: string; model: string; thinking: typeof THINKING[number];
  sessionId?: string; resources?: "inherit" | "minimal";
};
export type Report = {
  workerId: string; instanceId: string; taskId: string; reportId: string;
  sessionId?: string; sessionFile?: string; outcome: "settled" | "handled" | "failed" | "exited";
  aborted: boolean; summary: string; error?: string; captureIncomplete: boolean; summaryTruncated: boolean;
};
type Packet = Record<string, any>;
type Pending = {
  command: string; uncertain: boolean; timer: ReturnType<typeof setTimeout>;
  resolve: (packet: Packet) => void; reject: (error: Error) => void;
  apply?: (packet: Packet) => void;
};
export type WorkerOptions = {
  command?: string; prefixArgs?: string[]; requestMs?: number; shutdownMs?: number;
  captureBytes?: number; maxLineBytes?: number; env?: NodeJS.ProcessEnv;
};

export class RpcError extends Error {
  constructor(message: string, readonly requestId?: string, readonly unknownOutcome = false) { super(message); }
}

/** One controller owns one Pi child, including the sole stdout reader. */
export class Worker {
  readonly instanceId = randomUUID();
  readonly events: Capture;
  readonly stderr: Capture;
  readonly reports: Report[] = [];
  private child?: ChildProcessWithoutNullStreams;
  private pending = new Map<string, Pending>();
  private exited = false;
  private exitPromise: Promise<void>;
  private resolveExit!: () => void;
  private stopPromise?: Promise<ReturnType<Worker["snapshot"]>>;
  private closing = false;
  private protocolLoss = 0;
  private task?: { id: string; lastText: string; truncated: boolean; error?: string };
  private dispatching = false;
  private taskIds = new Set<string>();
  private queue = { steering: [] as string[], followUp: [] as string[] };
  private verified?: Packet;
  private fault?: string;
  private exitCode: number | null = null;
  private exitSignal: string | null = null;
  state: "starting" | "idle" | "working" | "stopping" | "stopped" | "failed" = "starting";

  constructor(readonly spec: StartSpec, private onReport: (report: Report) => void,
    private options: WorkerOptions = {}) {
    this.events = new Capture(options.captureBytes);
    this.stderr = new Capture(256 * 1024, 16 * 1024);
    this.exitPromise = new Promise(resolve => { this.resolveExit = resolve; });
  }

  async start() {
    const args = ["--mode", "rpc", "--provider", this.spec.provider, "--model", this.spec.model,
      "--thinking", this.spec.thinking, "--exclude-tools", TOOL_NAMES.join(",")];
    if (this.spec.sessionId) args.push("--session", this.spec.sessionId);
    if (this.spec.resources === "minimal") args.push("--no-extensions", "--no-mcp", "--no-skills", "--no-prompt-templates");
    this.child = spawn(this.options.command ?? "pi", [...(this.options.prefixArgs ?? []), ...args], {
      cwd: this.spec.cwd, env: { ...process.env, ...this.options.env, [WORKER_ENV]: "1" },
      stdio: ["pipe", "pipe", "pipe"], detached: process.platform !== "win32",
    });
    const child = this.child;
    child.once("error", () => {
      this.fault = "Worker process could not start";
      this.finishExit(null, null);
    });
    child.once("close", (code, signal) => this.finishExit(code, signal));
    child.stdin.on("error", () => this.transportFailure("Worker stdin failed; dispatched commands and completion may have unknown outcomes. Worker may still be running; inspect/stop it."));
    child.stdout.on("error", () => {
      this.protocolLoss++;
      this.transportFailure("Worker stdout failed; dispatched commands and completion may have unknown outcomes. Worker may still be running; inspect/stop it.");
    });
    child.stderr.on("error", () => {
      this.protocolLoss++;
      this.events.append({ type: "capture_error", reason: "Worker stderr capture failed" });
    });
    const stderrDecoder = new StringDecoder("utf8");
    child.stderr.on("data", chunk => this.stderr.append(stderrDecoder.write(chunk)));
    child.stderr.on("end", () => { const tail = stderrDecoder.end(); if (tail) this.stderr.append(tail); });
    // LF-only framing; retain partial bytes, with a strict upper bound even without LF.
    let buffer = Buffer.alloc(0), discarding = false;
    const limit = this.options.maxLineBytes ?? 8 * 1024 * 1024;
    child.stdout.on("data", (chunk: Buffer) => {
      let start = 0;
      while (start < chunk.length) {
        const end = chunk.indexOf(10, start);
        const piece = chunk.subarray(start, end < 0 ? chunk.length : end);
        if (!discarding && buffer.length + piece.length > limit) {
          this.protocolLoss++;
          this.events.append({ type: "capture_error", reason: "RPC record exceeded framing limit" });
          buffer = Buffer.alloc(0); discarding = true;
        }
        if (!discarding) buffer = Buffer.concat([buffer, piece]);
        if (end < 0) break;
        if (!discarding) this.line(buffer.toString("utf8").replace(/\r$/, ""));
        buffer = Buffer.alloc(0); discarding = false; start = end + 1;
      }
    });
    child.stdout.on("end", () => {
      if (buffer.length || discarding) { this.protocolLoss++; this.events.append({ type: "capture_error", reason: "Incomplete final RPC record" }); }
    });
    try {
      await this.verify();
      if (this.closing || this.exited) throw new Error("Worker closed during startup");
      this.state = "idle";
      return this.snapshot();
    } catch (error) {
      this.fault = error instanceof Error ? error.message : "Startup failed";
      await this.stop();
      throw error;
    }
  }

  private line(line: string) {
    let packet: Packet;
    try {
      packet = JSON.parse(line);
      if (!packet || typeof packet !== "object" || Array.isArray(packet) || typeof packet.type !== "string") throw new Error();
    } catch {
      this.protocolLoss++;
      this.events.append({ type: "capture_error", reason: "Invalid RPC JSON record (payload omitted)" });
      return;
    }
    this.events.append(packet);
    if (packet.type === "response") {
      const pending = this.pending.get(packet.id);
      if (!pending || packet.command !== pending.command || typeof packet.success !== "boolean") return;
      clearTimeout(pending.timer);
      this.pending.delete(packet.id);
      try { pending.apply?.(packet); }
      catch { this.fault = "Could not apply RPC response"; }
      if (packet.success) pending.resolve(packet);
      else pending.reject(new RpcError(clip(String(packet.error ?? "RPC command rejected"), 2000), packet.id));
      return;
    }
    if (packet.type === "queue_update" && Array.isArray(packet.steering) && Array.isArray(packet.followUp)) {
      this.queue = { steering: packet.steering.slice(0, 32).map((x: unknown) => clip(String(x), 2000)),
        followUp: packet.followUp.slice(0, 32).map((x: unknown) => clip(String(x), 2000)) };
    }
    if (packet.type === "agent_start" && !this.closing) this.state = "working";
    if (packet.type === "message_end" && packet.message?.role === "assistant" && this.task) {
      const text = Array.isArray(packet.message.content) ? packet.message.content
        .filter((block: Packet) => block?.type === "text" && typeof block.text === "string")
        .map((block: Packet) => block.text).join("\n") : "";
      this.task.lastText = clip(text, 24000);
      this.task.truncated = Buffer.byteLength(text) > 24000;
      if (["error", "aborted"].includes(packet.message.stopReason)) {
        this.task.error = clip(String(packet.message.errorMessage ?? packet.message.stopReason), 2000);
      } else this.task.error = undefined;
    }
    if (packet.type === "auto_retry_end" && packet.success === false && this.task) {
      this.task.error = clip(String(packet.finalError ?? "Provider retry failed"), 2000);
    }
    if (packet.type === "agent_settled") {
      if (!this.closing) this.state = this.fault ? "failed" : "idle";
      this.complete("settled", packet.aborted === true);
    }
    if (packet.type === "extension_ui_request" && ["confirm", "select", "input", "editor"].includes(packet.method)) {
      // No implicit approvals or hanging headless dialogs. Record and cancel them.
      this.events.append({ type: "ui_dialog_cancelled", id: packet.id, method: packet.method });
      this.write({ type: "extension_ui_response", id: packet.id, cancelled: true, confirmed: false });
    }
  }

  private write(packet: Packet, callback?: (error?: Error | null) => void) {
    try {
      const stdin = this.child?.stdin;
      if (!stdin || stdin.destroyed || !stdin.writable) throw new Error("Worker stdin unavailable");
      // Pending requests and command bytes are bounded. Node queues writes until drained.
      stdin.write(JSON.stringify(packet) + "\n", callback);
    } catch (error) { callback?.(error instanceof Error ? error : new Error("Write failed")); }
  }

  private rpc(command: Packet, apply?: Pending["apply"]): Promise<Packet> {
    if (this.exited || this.closing || this.fault) return Promise.reject(new Error(this.fault ?? "Worker is not running"));
    if (this.pending.size >= 32) return Promise.reject(new Error("Pending/uncertain request limit reached; inspect or stop worker"));
    const id = randomUUID();
    return new Promise((resolve, reject) => {
      const pending: Pending = { command: command.type, uncertain: false, resolve, reject, apply,
        timer: setTimeout(() => {
          pending.uncertain = true;
          reject(new RpcError("RPC response deadline exceeded; outcome unknown. Do not resend; inspect events/status.", id, true));
        }, this.options.requestMs ?? 30000) };
      this.pending.set(id, pending);
      this.write({ ...command, id }, error => {
        if (!error || !this.pending.has(id)) return;
        clearTimeout(pending.timer);
        pending.uncertain = true;
        reject(new RpcError("RPC write failed; outcome unknown. Do not resend.", id, true));
      });
    });
  }

  private async verify() {
    const { data } = await this.rpc({ type: "get_state" });
    if (!data || data.model?.provider !== this.spec.provider || data.model?.id !== this.spec.model ||
        data.thinkingLevel !== this.spec.thinking || typeof data.sessionId !== "string" ||
        (this.spec.sessionId && data.sessionId !== this.spec.sessionId) ||
        (this.verified && data.sessionId !== this.verified.sessionId)) {
      throw new Error("Effective model/thinking/session mismatch; no task dispatched");
    }
    this.verified = { sessionId: data.sessionId, sessionFile: data.sessionFile,
      model: { provider: data.model.provider, id: data.model.id }, thinking: data.thinkingLevel };
    if (data.isStreaming || data.isCompacting || data.pendingMessageCount) {
      throw new Error("Worker has active or queued work; no new task dispatched");
    }
  }

  async send(mode: "prompt" | "steer" | "follow_up", text: string, taskId?: string, signal?: AbortSignal) {
    signal?.throwIfAborted();
    if (!text.trim() || Buffer.byteLength(text) > 60000) throw new Error("text must be nonempty and at most 60000 UTF-8 bytes");
    if (this.state === "starting" || this.closing || this.exited || this.fault) throw new Error("Worker is not ready");
    if (this.dispatching || [...this.pending.values()].some(p => p.uncertain)) throw new Error("Dispatch or uncertain request pending; inspect before sending");
    if (mode === "prompt" && (!taskId || this.task || this.state !== "idle" || this.queue.steering.length || this.queue.followUp.length)) {
      throw new Error("New prompt requires a taskId and an idle worker with no assignment/queued work");
    }
    if (mode !== "prompt" && !this.task) throw new Error("steer/follow_up require an active assignment");
    if (mode === "prompt" && this.taskIds.has(taskId!)) throw new Error("taskId already used by this worker; use a new ID");
    if (mode === "prompt" && this.taskIds.size >= 256) throw new Error("Worker assignment limit reached (256); start a new worker");
    this.dispatching = true;
    try {
      if (mode === "prompt") {
        await this.verify();
        signal?.throwIfAborted();
        if (this.closing || this.exited) throw new Error("Worker closed before dispatch");
        this.taskIds.add(taskId!);
        this.task = { id: taskId!, lastText: "", truncated: false };
        this.state = "working";
      }
      const assignment = this.task;
      const packet = await this.rpc({ type: mode, message: text }, response => {
        // This callback also runs for late replies after the caller's deadline.
        if (mode !== "prompt" || this.task !== assignment) return;
        if (!response.success) { this.task = undefined; if (!this.closing) this.state = "idle"; }
        else if (response.data?.disposition === "handled") {
          if (!this.closing) this.state = "idle";
          this.complete("handled", false);
        }
      });
      return { workerId: this.spec.workerId, taskId: assignment?.id, requestId: packet.id,
        accepted: true, disposition: packet.data?.disposition, completed: false };
    } finally { this.dispatching = false; }
  }

  async abort() {
    const response = await this.rpc({ type: "abort" });
    // Native abort can continue queued instructions; do not clear or reassign them.
    return { workerId: this.spec.workerId, acknowledged: response.success,
      queueCleared: false, state: this.snapshot() };
  }

  private complete(outcome: Report["outcome"], aborted: boolean) {
    if (!this.task) return;
    const task = this.task;
    this.task = undefined;
    const report: Report = { workerId: this.spec.workerId, instanceId: this.instanceId, taskId: task.id,
      reportId: randomUUID(), sessionId: this.verified?.sessionId, sessionFile: this.verified?.sessionFile,
      outcome, aborted, summary: task.lastText, summaryTruncated: task.truncated,
      ...(task.error ? { error: task.error } : {}), captureIncomplete: this.incomplete() };
    this.reports.push(report);
    if (this.reports.length > 32) this.reports.shift();
    try { this.onReport(report); }
    catch { this.fault = "Report notification failed; report remains available through agent_read"; }
  }

  private transportFailure(message: string) {
    this.fault = message;
    this.rejectPending(message);
    if (!this.closing) {
      this.state = "failed";
      if (this.task) this.task.error = message;
      this.complete("failed", false);
    }
  }

  private rejectPending(message: string) {
    for (const [id, pending] of this.pending) {
      clearTimeout(pending.timer);
      pending.uncertain = true;
      pending.reject(new RpcError(message, id, true));
    }
  }

  private finishExit(code: number | null, signal: string | null) {
    if (this.exited) return;
    this.exited = true; this.exitCode = code; this.exitSignal = signal;
    this.state = this.closing ? "stopped" : "failed";
    this.rejectPending("Worker exited; dispatched commands without responses have unknown outcomes");
    if (this.task && !this.task.error) this.task.error = "Process exited before settlement";
    this.complete("exited", false);
    this.resolveExit();
  }

  private incomplete() {
    return this.protocolLoss > 0 || this.events.dropped > 0 || this.events.truncated > 0;
  }

  snapshot() {
    return { workerId: this.spec.workerId, instanceId: this.instanceId, pid: this.child?.pid,
      cwd: this.spec.cwd, resources: this.spec.resources ?? "inherit", state: this.state,
      verified: this.verified, taskId: this.task?.id, queue: this.queue,
      requests: [...this.pending].map(([id, p]) => ({ id, command: p.command, outcome: p.uncertain ? "unknown" : "pending" })),
      latestReportId: this.reports.at(-1)?.reportId, retainedReports: this.reports.length,
      captureIncomplete: this.incomplete(), protocolLoss: this.protocolLoss,
      stderrDropped: this.stderr.dropped, fault: this.fault,
      exit: this.exited ? { code: this.exitCode, signal: this.exitSignal } : undefined };
  }

  read(view: "report" | "events" | "stderr", options: { reportId?: string; cursor?: string; maxBytes?: number }) {
    if (view !== "report") return (view === "events" ? this.events : this.stderr).read(options.cursor, options.maxBytes);
    if (options.cursor) throw new Error("Report reads use reportId, not a cursor");
    const report = options.reportId ? this.reports.find(r => r.reportId === options.reportId) : this.reports.at(-1);
    if (!report) throw new Error("Report not found or no longer retained; consult saved session evidence");
    return report;
  }

  stop() {
    if (this.stopPromise) return this.stopPromise;
    this.closing = true;
    this.state = "stopping";
    this.stopPromise = this.shutdown();
    return this.stopPromise;
  }

  private async shutdown() {
    const child = this.child;
    if (!child) { this.state = "stopped"; return this.snapshot(); }
    const wait = async () => {
      let timer: ReturnType<typeof setTimeout>;
      await Promise.race([this.exitPromise, new Promise<void>(resolve => { timer = setTimeout(resolve, this.options.shutdownMs ?? 1000); })]);
      clearTimeout(timer!);
    };
    const signalGroup = (signal: NodeJS.Signals) => {
      if (!child.pid) return;
      try {
        if (process.platform !== "win32") process.kill(-child.pid, signal);
        else if (!this.exited) child.kill(signal);
      } catch (error) { if ((error as NodeJS.ErrnoException).code !== "ESRCH") this.fault = "Process-group cleanup could not be confirmed"; }
    };
    child.stdin.end();
    await wait();
    // Own the spawned group, not just its leader; worker tools may spawn children.
    signalGroup("SIGTERM");
    if (!this.exited) await wait();
    signalGroup("SIGKILL");
    if (!this.exited) await wait();
    this.state = this.exited ? "stopped" : "failed";
    if (!this.exited) this.fault = "Worker exit not confirmed; do not assume cleanup succeeded";
    return this.snapshot();
  }
}
