/** Public wire/state definitions; runtime validators live with their components. */
export type JSONValue = null | boolean | number | string | JSONValue[] | { [key: string]: JSONValue };
export type ComponentPayload = { type: "component"; data: { name: string; id: string; props: JSONValue } };
export type EventPayload = { type: "event"; data: { name: string; target: string; detail: JSONValue } };
export type Payload = ComponentPayload | EventPayload;
export type Message = { id: string; role: "user" | "agent"; content: ComponentPayload };
export type History = { messages: Message[]; componentStates: Record<string, JSONValue> };
export type Instance = { name: string; props: any; state?: any; contracts?: Set<string> };
export type ComponentHandle = { element: HTMLElement; snapshot?: () => JSONValue; dispose?: () => void };
export type ComponentContext = { componentId: string; state?: JSONValue; history: History;
  changed: () => void; canSend: () => boolean; appendRevision: (props: FormProps) => void };
export type ComponentDefinition = {
  contract: string;
  validate: (props: unknown) => any;
  validateState?: (props: any, state: unknown) => any;
  validateHistory?: (history: History) => void;
  events?: Record<string, (detail: unknown, instance: Instance) => any>;
  create: (props: any, context: ComponentContext) => ComponentHandle;
};
export type Registry = Readonly<Record<string, ComponentDefinition>>;
export type Choice = { value: string; label: string };
export type FormField = { name: string; label: string; required: boolean } &
  ({ kind: "text"; minLength?: number; maxLength?: number } | { kind: "choice"; choices: Choice[] });
export type FormProps = { title: string; submitLabel: string; fields: FormField[]; initialValues: Record<string, string>;
  revision: null | { originComponentId: string; previousSubmissionId: string } };
export type Submission = { submissionId: string; previousSubmissionId: string | null; values: Record<string, string> };
export type FormState = { values: Record<string, string>; submission: Submission | null };
export type ChatData = { title: string; agentLabel: string; userLabel: string; inputLabel: string;
  sendLabel: string; placeholder: string; emptyMessage: string };
export type ChatSnapshot = History & { version: 2; id: string; settings: ChatData;
  events: EventPayload[]; composer: string; pending: boolean };
export type StarterSnapshot = { version: 2; mode: "sample" | "live"; chat: ChatSnapshot };
