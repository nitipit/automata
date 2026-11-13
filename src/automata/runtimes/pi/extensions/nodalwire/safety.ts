import { constants } from "node:fs";
import { open } from "node:fs/promises";

export type NativeMessage = {
  id: string; sender: string; network: string; reply_to?: string; payload: Uint8Array;
};

export function validName(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(value);
}

const validId = (value: unknown): value is string =>
  typeof value === "string" && /^[0-9a-f]{32}$/.test(value);

/** Validate native routing metadata without echoing peer data or accessor errors. */
export function validateNativeMessage(value: unknown): asserts value is NativeMessage {
  try {
    if (value !== null && typeof value === "object") {
      const message = value as NativeMessage;
      if (validId(message.id) && validName(message.sender) && validName(message.network) &&
          (message.reply_to === undefined || validId(message.reply_to)) &&
          message.payload instanceof Uint8Array) return;
    }
  } catch { /* Untrusted accessors must not escape into diagnostics. */ }
  throw new Error("Invalid native message metadata");
}

const transportCodes = new Set([
  "invalid_name", "admission_denied", "duplicate_name", "not_registered", "invalid_command",
  "invalid_destination", "invalid_network", "network_not_found", "join_denied", "not_member",
  "destination_not_member", "payload_too_large", "invalid_id", "invalid_reply_to", "route_denied",
  "destination_unavailable", "destination_full", "unsupported_version", "pending_full",
  "local_queue_full", "invalid_receipt", "closed", "connection_failed",
]);
const operations = new Set(["connect", "disconnect", "send", "join", "leave", "request", "reply", "receive", "close"]);

/** No raw messages, causes, operation strings or arbitrary abort reasons escape. */
export function safeTransportError(error: unknown, operation: string): Error {
  const label = operations.has(operation) ? operation : "operation";
  let code: string | undefined;
  let name: unknown;
  try {
    if (error !== null && typeof error === "object") {
      const candidate = error as { code?: unknown; name?: unknown };
      if (typeof candidate.code === "string" && transportCodes.has(candidate.code)) code = candidate.code;
      name = candidate.name;
    }
  } catch { /* Treat hostile error accessors as an unknown failure. */ }
  if (code === "closed" || code === "connection_failed" || code === "invalid_receipt") {
    return new Error(`NodalWire ${label} failed (${code}); effect uncertain. No automatic retry.`);
  }
  if (code) return new Error(`NodalWire ${label} failed (${code}). No automatic retry.`);
  if (name === "ReceiptTimeout") return new Error(`NodalWire ${label} timed out; effect uncertain. No automatic retry.`);
  if (name === "AbortError") return new Error(`NodalWire ${label} cancelled; effect uncertain. No automatic retry.`);
  return new Error(`NodalWire ${label} failed; effect uncertain. No automatic retry.`);
}

const CONFIG_LIMIT = 32 * 1024;
const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value) &&
  Object.getPrototypeOf(value) === Object.prototype;
const exactKeys = (value: Record<string, unknown>, keys: string[]) =>
  Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const validCredential = (value: unknown): value is string =>
  typeof value === "string" && /^[\x21-\x7e]{1,1024}$/.test(value);

type Alias = { endpoint: string; network: string; env: string };

/** Bounded, no-follow read of an explicitly selected operator configuration. */
async function readAliases(path: string): Promise<Record<string, Alias>> {
  // NONBLOCK also prevents an accidentally configured FIFO from blocking open().
  const file = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const stat = await file.stat();
    if (!stat.isFile() || stat.size > CONFIG_LIMIT ||
        (process.platform !== "win32" &&
          (stat.uid !== process.getuid?.() || (stat.mode & 0o022) !== 0))) throw new Error();
    const buffer = Buffer.alloc(CONFIG_LIMIT + 1);
    let size = 0;
    while (size < buffer.length) {
      const { bytesRead } = await file.read(buffer, size, buffer.length - size, null);
      if (!bytesRead) break;
      size += bytesRead;
    }
    if (size > CONFIG_LIMIT) throw new Error();
    const config: unknown = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(buffer.subarray(0, size)));
    if (!object(config) || !exactKeys(config, ["aliases"]) || !object(config.aliases)) throw new Error();
    const aliases = config.aliases;
    if (Object.keys(aliases).length > 64) throw new Error();
    for (const [name, entry] of Object.entries(aliases)) {
      if (!validName(name) || !object(entry) || !exactKeys(entry, ["endpoint", "network", "env"]) ||
          typeof entry.endpoint !== "string" || entry.endpoint.length === 0 ||
          !validName(entry.network) || typeof entry.env !== "string" ||
          !/^[A-Za-z_][A-Za-z0-9_]*$/.test(entry.env)) throw new Error();
    }
    return aliases as Record<string, Alias>;
  } finally { await file.close(); }
}

/**
 * Resolve only an operator-allowlisted environment alias for this exact binding.
 * No factory I/O, retained secrets, trimming, fallback or shell execution. Same-user
 * code is not sandboxed; JavaScript credential strings cannot be securely erased.
 * Callback errors intentionally propagate internally for safeTransportError wrapping.
 */
export async function withJoinCredential<T>(
  configPath: string | undefined,
  ref: string | undefined,
  binding: { endpoint: string; network: string },
  use: (credential?: string) => Promise<T>,
  env: NodeJS.ProcessEnv = process.env,
): Promise<T> {
  if (ref === undefined) return use(undefined);
  let credential: string;
  try {
    if (!validName(ref) || typeof configPath !== "string" || !configPath) throw new Error();
    const aliases = await readAliases(configPath);
    if (!Object.hasOwn(aliases, ref)) throw new Error();
    const alias = aliases[ref];
    if (alias.endpoint !== binding.endpoint || alias.network !== binding.network ||
        !Object.hasOwn(env, alias.env)) throw new Error();
    const value = env[alias.env];
    if (!validCredential(value)) throw new Error();
    credential = value;
  } catch {
    throw new Error("NodalWire join credential configuration or reference is invalid");
  }
  return use(credential);
}
