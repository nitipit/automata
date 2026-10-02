import { cloneJSON, ContractError, requireId, requireRecord } from "./contracts.js";
import type { DefinitionSource, DraftInstance, DraftSnapshot } from "./types.js";

/** Structural admission only; source provenance is the trusted loader's job. */
export function validateSnapshot(value: unknown): DraftSnapshot {
  const data = requireRecord(value, ["version", "definitions", "layout"], "Draft snapshot");
  if (data.version !== 1 || !Array.isArray(data.definitions) || !Array.isArray(data.layout)) {
    throw new ContractError("Draft snapshot", "Expected version 1, definitions and ordered layout");
  }
  const definitionIds = new Set<string>();
  const definitions: DefinitionSource[] = data.definitions.map(item => {
    const record = requireRecord(item, ["id", "source", "css"], "Definition source");
    const id = requireId(record.id);
    if (definitionIds.has(id) || typeof record.source !== "string" || !record.source.trim() ||
        typeof record.css !== "string") {
      throw new ContractError("Definition source", "Unique ID, nonempty factory source and CSS string required");
    }
    definitionIds.add(id);
    return { id, source: record.source, css: record.css };
  });
  const instanceIds = new Set<string>();
  const layout: DraftInstance[] = data.layout.map(item => {
    const record = requireRecord(item, ["id", "definition", "props", "state"], "Draft instance");
    const id = requireId(record.id);
    const definition = requireId(record.definition);
    if (instanceIds.has(id) || !definitionIds.has(definition)) {
      throw new ContractError("Draft instance", "Unique instance ID and known definition required");
    }
    instanceIds.add(id);
    return { id, definition, props: cloneJSON(record.props), state: cloneJSON(record.state) };
  });
  return { version: 1, definitions, layout };
}
