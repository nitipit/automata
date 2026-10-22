import { randomUUID } from "node:crypto";

export function clip(text: string, bytes: number): string {
  const buffer = Buffer.from(text);
  if (buffer.length <= bytes) return text;
  // Avoid ending with a partial UTF-8 character.
  return new TextDecoder("utf-8", { fatal: false }).decode(buffer.subarray(0, bytes)).replace(/\uFFFD$/, "");
}

/** Bounded, non-consuming evidence log. Cursors belong to one process/stream. */
export class Capture {
  private readonly identity = randomUUID();
  private rows: { sequence: number; value: unknown; bytes: number }[] = [];
  private next = 0;
  private bytes = 0;
  dropped = 0;
  truncated = 0;

  constructor(private capacity = 1024 * 1024, private maxRecord = 60 * 1024,
    private maxRecords = 2048) {}

  append(value: unknown) {
    const serialized = JSON.stringify(value);
    let bytes = Buffer.byteLength(serialized);
    if (bytes > this.maxRecord) {
      value = { truncated: true, originalBytes: bytes, preview: clip(serialized, Math.floor(this.maxRecord / 2)) };
      bytes = Buffer.byteLength(JSON.stringify(value));
      this.truncated++;
    }
    this.rows.push({ sequence: this.next++, value, bytes });
    this.bytes += bytes;
    while (this.bytes > this.capacity || this.rows.length > this.maxRecords) {
      const old = this.rows.shift()!;
      this.bytes -= old.bytes;
      this.dropped++;
    }
  }

  private cursor(sequence: number) {
    return Buffer.from(JSON.stringify([this.identity, sequence])).toString("base64url");
  }

  read(cursor: string | undefined, maxBytes = 16000) {
    if (!Number.isSafeInteger(maxBytes) || maxBytes < 256 || maxBytes > 128 * 1024) {
      throw new Error("maxBytes must be an integer between 256 and 131072");
    }
    const earliest = this.rows[0]?.sequence ?? this.next;
    let position = earliest;
    if (cursor !== undefined) {
      if (cursor.length > 256) throw new Error("Invalid cursor");
      let decoded;
      try { decoded = JSON.parse(Buffer.from(cursor, "base64url").toString("utf8")); }
      catch { throw new Error("Invalid cursor"); }
      if (!Array.isArray(decoded) || decoded.length !== 2 || decoded[0] !== this.identity ||
          !Number.isSafeInteger(decoded[1]) || decoded[1] < 0 || decoded[1] > this.next) {
        throw new Error("Cursor belongs to another worker/stream or is invalid");
      }
      position = decoded[1];
    }
    const gap = position < earliest;
    position = Math.max(position, earliest);
    const records: unknown[] = [];
    let used = 0, requiredBytes: number | undefined;
    for (const row of this.rows) {
      if (row.sequence < position) continue;
      const record = { sequence: row.sequence, value: row.value };
      const readBytes = Buffer.byteLength(JSON.stringify(record)) + 1;
      if (used + readBytes > maxBytes) { requiredBytes = readBytes; break; }
      records.push(record);
      used += readBytes;
      position = row.sequence + 1;
    }
    return { records, nextCursor: this.cursor(position), earliestCursor: this.cursor(earliest),
      hasMore: position < this.next, gap, droppedRecords: this.dropped, truncatedRecords: this.truncated,
      ...(requiredBytes && records.length === 0 ? { blocked: true, requiredBytes } : {}) };
  }
}
