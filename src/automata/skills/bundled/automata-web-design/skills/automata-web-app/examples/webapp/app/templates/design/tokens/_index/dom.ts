/** Small native-DOM helpers shared by the page-local specimens. */
export function element(tag: string, className = "", text = ""): HTMLElement {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

export function materialLabel(name: string, value: string): HTMLElement {
  const label = element("div", "material-label");
  label.append(element("span", "", name), element("code", "", value));
  return label;
}
