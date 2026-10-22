import { createRequire } from "node:module";

// Edictor 0.4.0 publishes CommonJS; native Node ESM cannot use its named imports.
const { Model, defineField } = createRequire(import.meta.url)("edictor") as typeof import("edictor");

export const PROTOCOL_VERSION = 2;
export const MAX_PACKET_BYTES = 64 * 1024;
export const MAX_CONTENT_BLOCKS = 64;
const MAX_FIELD_BYTES = 48 * 1024;
const MAX_DETAILS_BYTES = 8 * 1024;
const encoder = new TextEncoder();
const decoder = new TextDecoder("utf-8", { fatal: true });
const bytes = (value: string) => encoder.encode(value).byteLength;

/** Inline base64 image validation is structural, not proof a provider can decode it. */
export type ContentBlock =
  | { type: "text"; text: string; textSignature?: string }
  | { type: "image"; data: string; mimeType: string };
export type PeerMessage = { content: string | ContentBlock[]; display: boolean; details?: unknown };
/** Native Pi options: omitted fields stay omitted, not rewritten into presets. */
export type MessageOptions = { triggerTurn?: boolean; deliverAs?: "steer" | "followUp" | "nextTurn" };
export type Packet = { version: 2; message: PeerMessage; options?: MessageOptions };

const stringField = (required = true, limit = MAX_FIELD_BYTES) =>
  defineField({ required }).instance("string")
    .assert((value: string) => bytes(value) <= limit, "String exceeds field byte limit");

export class TextBlock extends Model {}
TextBlock.define({
  type: defineField({ required: true }).assert((value: unknown) => value === "text"),
  text: stringField(),
  textSignature: stringField(false),
}, { strict: true });

export class ImageBlock extends Model {}
ImageBlock.define({
  type: defineField({ required: true }).assert((value: unknown) => value === "image"),
  data: stringField().assert((value: string) =>
    value.length > 0 && value.length % 4 === 0 &&
    /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value),
  "Expected base64 image data"),
  mimeType: stringField(true, 128).regexp(/^image\/[A-Za-z0-9.+-]+$/),
}, { strict: true });

function declaredFields(model: typeof Model, value: unknown): void {
  if (value === null || typeof value !== "object" || Array.isArray(value) ||
      Object.getPrototypeOf(value) !== Object.prototype) throw new Error("Expected a JSON object");
  // Edictor's strict check admits inherited Object names such as __proto__.
  // Derive this guard from the public schema, rather than duplicate field lists.
  const fields = model.field;
  if (Object.keys(value).some(key => !Object.hasOwn(fields, key))) throw new Error("Unknown field");
}

function validContent(value: unknown): boolean {
  if (typeof value === "string") return bytes(value) <= MAX_FIELD_BYTES;
  if (!Array.isArray(value) || value.length > MAX_CONTENT_BLOCKS) return false;
  try {
    for (const block of value) {
      if (block?.type === "text") { declaredFields(TextBlock, block); TextBlock.validate(block); }
      else if (block?.type === "image") { declaredFields(ImageBlock, block); ImageBlock.validate(block); }
      else return false;
    }
    return true;
  } catch { return false; }
}

function validDetails(value: unknown): boolean {
  // Details are arbitrary JSON, not only objects. Bound traversal before stringify.
  let nodes = 0;
  const visit = (item: unknown, depth: number): boolean => {
    if (++nodes > 2048 || depth > 16) return false;
    if (item === null || typeof item === "boolean" || typeof item === "string") return true;
    if (typeof item === "number") return Number.isFinite(item);
    if (Array.isArray(item)) return item.every(child => visit(child, depth + 1));
    if (typeof item !== "object" || Object.getPrototypeOf(item) !== Object.prototype) return false;
    return Object.values(item).every(child => visit(child, depth + 1));
  };
  try { return visit(value, 0) && bytes(JSON.stringify(value)) <= MAX_DETAILS_BYTES; }
  catch { return false; }
}

export class Message extends Model {}
Message.define({
  content: defineField({ required: true }).assert(validContent, "Invalid or oversized content"),
  display: defineField({ required: true }).instance("boolean"),
  details: defineField().assert(validDetails, "Details must be bounded JSON"),
}, { strict: true });

export class Options extends Model {}
Options.define({
  triggerTurn: defineField().instance("boolean"),
  deliverAs: defineField().assert((value: unknown) =>
    value === "steer" || value === "followUp" || value === "nextTurn"),
}, { strict: true });

export class Envelope extends Model {}
Envelope.define({
  version: defineField({ required: true }).assert((value: unknown) => value === PROTOCOL_VERSION),
  message: defineField({ required: true }).model(Message),
  options: defineField().model(Options),
}, { strict: true });

/**
 * Validate the Edictor v2 schema plus own-field guards, rejecting v1/unknown fields.
 * Details are JSON bounded to 8 KiB, depth 16 and 2048 visited values; content has
 * at most 64 blocks, 48 KiB per text/image-data field and 128-byte image MIME types.
 * @returns The original object so absent native options are not normalized away.
 * @throws On invalid structure/fields; encoded envelope size is checked separately.
 */
export function validatePacket(value: unknown): Packet {
  declaredFields(Envelope, value);
  const packet = value as Packet;
  declaredFields(Message, packet.message);
  if (Object.hasOwn(packet, "options")) declaredFields(Options, packet.options);
  Envelope.validate(value as object);
  // Return the original object, not Edictor's normalized copy: omitted native
  // options must remain omitted. Callers only use this after strict validation.
  return value as Packet;
}

/** Encode validated UTF-8 JSON, enforcing the aggregate 64 KiB bound without truncation. */
export function encodeMessage(message: PeerMessage, options?: MessageOptions): Uint8Array {
  const packet: Packet = { version: PROTOCOL_VERSION, message };
  if (options !== undefined) packet.options = options;
  validatePacket(packet);
  const payload = encoder.encode(JSON.stringify(packet));
  if (payload.byteLength > MAX_PACKET_BYTES) throw new Error("Envelope exceeds 64 KiB");
  return payload;
}

/** Check size before fatal UTF-8 decoding/JSON parsing; no fallback, conversion or replay. */
export function decodeMessage(payload: Uint8Array): Packet {
  if (!(payload instanceof Uint8Array) || payload.byteLength > MAX_PACKET_BYTES) {
    throw new Error("Invalid or oversized envelope");
  }
  return validatePacket(JSON.parse(decoder.decode(payload)));
}
