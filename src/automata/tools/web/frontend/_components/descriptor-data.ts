// Read only the keys a widget explicitly names; do not call getters or coerce values.
function ownValue(data: unknown, key: string): unknown {
  return data !== null && typeof data === "object" ? Object.getOwnPropertyDescriptor(data, key)?.value : undefined;
}

export function stringData(data: unknown, key: string): string | undefined {
  const value = ownValue(data, key);
  return typeof value === "string" ? value : undefined;
}

export function booleanData(data: unknown, key: string): boolean | undefined {
  const value = ownValue(data, key);
  return typeof value === "boolean" ? value : undefined;
}

export function rejectChildren(tag: string, children: readonly HTMLElement[]): void {
  if (children.length) throw new TypeError(`${tag} does not accept _children`);
}
