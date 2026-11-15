/** Bounded, one-attempt HTTP connector to the existing Python app, never a server. */
export type Effects = "none" | "unknown";
export class ConnectorError extends Error {
  constructor(public code: string, message: string, public effects: Effects) {
    super(message);
    this.name = "ConnectorError";
  }
}
export interface ConnectorConfig { origin: string; token: string }
export type Fetch = typeof globalThis.fetch;
const MAX_RESPONSE_BYTES = 64 * 1024;

/** Never include configuration values or native fetch errors in model-facing errors. */
export function validateConfig(config: ConnectorConfig): ConnectorConfig {
  let url: URL;
  try { url = new URL(config.origin); } catch { throw new ConnectorError("configuration", "Invalid connector origin", "none"); }
  if (url.protocol !== "http:" || url.hostname !== "127.0.0.1" || url.username || url.password ||
      url.pathname !== "/" || url.search || url.hash || !config.token || /[\r\n]/.test(config.token)) {
    throw new ConnectorError("configuration", "Connector requires a bare http://127.0.0.1 origin and separate credential", "none");
  }
  return { origin: url.origin, token: config.token };
}

export class Connector {
  private readonly active = new Set<AbortController>();
  private closed = false;
  constructor(private readonly fetcher: Fetch = globalThis.fetch) {}

  /** Idempotent; cancels local waits, not browser JavaScript or accepted host operations. */
  close(): void {
    this.closed = true;
    for (const controller of this.active) controller.abort();
    this.active.clear();
  }

  async post(config: ConnectorConfig, path: string, payload: unknown, timeoutMs: number, signal?: AbortSignal): Promise<unknown> {
    if (this.closed) throw new ConnectorError("closed", "Connector is closed", "none");
    if (signal?.aborted) throw new ConnectorError("cancelled", "Cancelled before dispatch", "none");
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 125_000) {
      throw new ConnectorError("validation", "Invalid connector deadline", "none");
    }
    const checked = validateConfig(config);
    if (!/^\/[a-z0-9_/-]+$/.test(path)) throw new ConnectorError("validation", "Invalid connector route", "none");
    const controller = new AbortController();
    this.active.add(controller);
    let expired = false;
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    const timer = setTimeout(() => { expired = true; controller.abort(); }, timeoutMs);
    let dispatched = false;
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    // Race also bounds collaborators which fail to honor AbortSignal.
    let rejectAbort: (reason: unknown) => void;
    const cancelled = new Promise<never>((_resolve, reject) => { rejectAbort = reject; });
    const onAbort = () => {
      void reader?.cancel().catch(() => {});
      rejectAbort(new ConnectorError(expired ? "timeout" : "cancelled",
        `${expired ? "Deadline exceeded" : "Cancelled"}; accepted operations may still run. Do not retry blindly.`, dispatched ? "unknown" : "none"));
    };
    controller.signal.addEventListener("abort", onAbort, { once: true });
    try {
      const body = JSON.stringify(payload);
      if (Buffer.byteLength(body) > 64 * 1024) throw new ConnectorError("validation", "Request exceeds 64 KiB", "none");
      const operation = async () => {
        dispatched = true;
        const response = await this.fetcher(checked.origin + path, {
          method: "POST", redirect: "error", signal: controller.signal,
          headers: { "Authorization": `Bearer ${checked.token}`, "Content-Type": "application/json", "User-Agent": "Automata/1.0" }, body,
        });
        if (!response.ok) {
          await response.body?.cancel();
          throw new ConnectorError("http_error", `Connector HTTP ${response.status}; operation outcome is unconfirmed`, "unknown");
        }
        reader = response.body?.getReader();
        if (controller.signal.aborted) { void reader?.cancel().catch(() => {}); controller.signal.throwIfAborted(); }
        if (!reader) throw new ConnectorError("protocol", "Connector returned no JSON body", "unknown");
        const chunks: Uint8Array[] = [];
        let size = 0;
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            size += value.byteLength;
            if (size > MAX_RESPONSE_BYTES) throw new ConnectorError("protocol", "Connector response exceeds 64 KiB; outcome unconfirmed", "unknown");
            chunks.push(value);
          }
          try { return JSON.parse(Buffer.concat(chunks).toString("utf8")); }
          catch { throw new ConnectorError("protocol", "Connector returned invalid JSON; outcome unconfirmed", "unknown"); }
        } finally {
          await reader.cancel().catch(() => {});
          reader.releaseLock();
        }
      };
      return await Promise.race([operation(), cancelled]);
    } catch (error) {
      if (error instanceof ConnectorError) throw error;
      if (controller.signal.aborted) {
        throw new ConnectorError(expired ? "timeout" : "cancelled", "Local wait ended; operation may still run. Do not retry blindly.", dispatched ? "unknown" : "none");
      }
      throw new ConnectorError("transport", "Connector transport failed; outcome unconfirmed. Do not retry blindly.", dispatched ? "unknown" : "none");
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
      controller.signal.removeEventListener("abort", onAbort);
      this.active.delete(controller);
    }
  }
}
