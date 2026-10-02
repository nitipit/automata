/** Public draft data is JSON; executable definitions are admitted separately. */
export type JSONValue = null | boolean | number | string | JSONValue[] |
  { [key: string]: JSONValue };
export type DefinitionSource = { id: string; source: string; css: string };
export type DraftInstance = {
  id: string;
  definition: string;
  props: JSONValue;
  state: JSONValue;
};
export type DraftSnapshot = {
  version: 1;
  definitions: DefinitionSource[];
  layout: DraftInstance[];
};
export type ComponentContext = {
  id: string;
  state: JSONValue;
  emit(name: string, value: unknown): void;
  changed(): void;
};
export type ComponentHandle = {
  element: HTMLElement;
  snapshot(): JSONValue;
  dispose(): void;
};
export type ComponentDefinition = {
  validateProps(value: unknown): JSONValue;
  validateState(props: JSONValue, value: unknown): JSONValue;
  events: Record<string, (value: unknown) => JSONValue>;
  /** Validate an incoming update and return new state without mutating inputs. */
  update(props: JSONValue, state: JSONValue, value: unknown): JSONValue;
  create(props: JSONValue, context: ComponentContext): ComponentHandle;
};
export type ComponentEvent = {
  id: string;
  name: string;
  payload: JSONValue;
  isCurrent(): boolean;
};
