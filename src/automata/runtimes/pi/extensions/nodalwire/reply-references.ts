import { randomUUID } from "node:crypto";
import { validateNativeMessage, type NativeMessage } from "./safety.ts";

type Entry = { generation: number; expires: number; incoming: NativeMessage };

/**
 * Bounded, one-dispatch routing capabilities, not a request correlation engine.
 * Expiry is monotonic and never refreshed. Callers clear synchronously at lifecycle
 * boundaries and validate/encode/check cancellation before consuming a reference.
 */
export class ReplyReferences {
  private readonly entries = new Map<string, Entry>();
  private readonly capacity: number;
  private readonly ttlMs: number;
  private readonly now: () => number;

  constructor({ capacity = 128, ttlMs = 300_000, now = () => performance.now() }:
    { capacity?: number; ttlMs?: number; now?: () => number } = {}) {
    if (!Number.isSafeInteger(capacity) || capacity <= 0 || !Number.isFinite(ttlMs) || ttlMs <= 0 ||
        typeof now !== "function") throw new Error("Invalid reply reference limits");
    this.capacity = capacity;
    this.ttlMs = ttlMs;
    this.now = now;
  }

  private expire(time: number): void {
    for (const [ref, entry] of this.entries) {
      if (time >= entry.expires) this.entries.delete(ref);
    }
  }

  add(generation: number, incoming: NativeMessage): string | undefined {
    validateNativeMessage(incoming);
    if (!Number.isSafeInteger(generation)) throw new Error("Invalid reply reference generation");
    const time = this.now();
    this.expire(time);
    if (this.entries.size >= this.capacity) return undefined;
    let ref: string;
    do { ref = randomUUID(); } while (this.entries.has(ref));
    // Never retain incoming content or the caller's mutable metadata object.
    const metadata = Object.freeze({
      id: incoming.id, sender: incoming.sender, network: incoming.network,
      ...(incoming.reply_to !== undefined ? { reply_to: incoming.reply_to } : {}),
      payload: new Uint8Array(0),
    });
    this.entries.set(ref, { generation, expires: time + this.ttlMs, incoming: metadata });
    return ref;
  }

  /** Atomic single-use lookup; callers never restore references after dispatch. */
  take(generation: number, replyRef: string): NativeMessage {
    this.expire(this.now());
    const entry = this.entries.get(replyRef);
    if (!entry || entry.generation !== generation) throw new Error("Reply reference is unavailable or expired");
    this.entries.delete(replyRef);
    return entry.incoming;
  }

  delete(replyRef: string): void { this.entries.delete(replyRef); }

  invalidateNetwork(generation: number, network: string): void {
    this.expire(this.now());
    for (const [ref, entry] of this.entries) {
      if (entry.generation === generation && entry.incoming.network === network) this.entries.delete(ref);
    }
  }

  clear(): void { this.entries.clear(); }
}
