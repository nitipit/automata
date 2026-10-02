/** Optional small runtime; no registration, connection or restoration on import. */
export { createPlayspace } from "./render.js";
export { evaluateTrustedDefinition } from "./definitions.js";
export { validateSnapshot } from "./state.js";
export { createCacheRecovery } from "./recovery.js";
export { createPlayspaceRouter } from "./transport.js";
export { ContractError, cloneJSON, isRecord, requireRecord } from "./contracts.js";
export type { JSONValue, DefinitionSource, DraftInstance, DraftSnapshot,
  ComponentDefinition, ComponentContext, ComponentHandle, ComponentEvent } from "./types.js";
