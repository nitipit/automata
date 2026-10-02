import { ContractError, isRecord } from "./contracts.js";
import { validateChatSnapshot } from "./chat-state.js";
import { builtins } from "./registry.js";
import type { Registry, StarterSnapshot } from "./types.js";

/** Optional starter envelope only; components own all payload/state semantics. */
export function validateStarterSnapshot(value: unknown, registry: Registry = builtins): StarterSnapshot {
  if (!isRecord(value) || Object.keys(value).some(key => !["version", "mode", "chat"].includes(key)) ||
    value.version !== 2 || !["sample", "live"].includes(value.mode)) {
    throw new ContractError("automata-playspace/lib/state.js: PlayspaceChatSnapshot v2", { snapshot: "Expected {version:2,mode:'sample'|'live',chat:ChatSnapshotV2}" });
  }
  return { version: 2, mode: value.mode, chat: validateChatSnapshot(value.chat, registry) };
}
