import type { Message, ComponentDefinition, ComponentContext, ChatData, ComponentHandle } from "./types.js";

/** One trusted component construction path. No content/event-specific UI branches. */
export function renderMessage(item: Message, definition: ComponentDefinition,
  context: Omit<ComponentContext, "componentId">, labels: ChatData): { element: HTMLElement; handle: ComponentHandle } {
  const element = document.createElement("article");
  element.className = "message";
  element.setAttribute("data-role", item.role);
  element.setAttribute("data-message-id", item.id);
  const label = document.createElement("strong");
  label.textContent = item.role === "user" ? labels.userLabel : labels.agentLabel;
  let live = true;
  const created = definition.create(item.content.data.props, {
    ...context, componentId: item.content.data.id,
    changed: () => { if (live) context.changed(); },
    canSend: () => live && context.canSend(),
    appendRevision: props => { if (live) context.appendRevision(props); },
  });
  const handle = { ...created, dispose: () => { live = false; created.dispose?.(); } };
  created.element.id = item.content.data.id;
  element.append(label, created.element);
  return { element, handle };
}
