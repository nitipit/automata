import { createComponentRegistry } from "../_components/create";
import { ChatMessage } from "../chat-message";
// The private sources are bundled alongside the public entry, then the
// fixture imports the public entry by the same URL as generated UI.
import "../ui";

function check(condition, description) {
  if (!condition) throw new Error(description);
}

function rejects(operation, pattern) {
  try { operation(); }
  catch (error) {
    check(error instanceof TypeError && pattern.test(error.message), `unexpected error: ${error}`);
    return;
  }
  throw new Error(`expected error matching ${pattern}`);
}

export async function run() {
  const ui = await import("/assets/ui.js");
  const { createComponent, Card, Button, Field, Select, Markdown, CodeBlock } = ui;
  check(!("ChatMessage" in ui) && !("createComponentRegistry" in ui), "public entry leaks an internal API");

  let executed = 0;
  const label = "<img src=x onerror=alert(1)>";
  const buttonDescriptor = {
    _class: "ui-button",
    _data: {
      text: label, onclick: () => executed++, attributes: { title: "do not reflect" },
      id: "do not reflect", innerHTML: "<img src=x>", get disabled() { executed++; return true; },
    },
  };
  const fieldDescriptor = { _class: "ui-field", _data: { label: "Name", value: "Ada", required: true } };
  const source = "<script>throw 1</script>";
  const codeDescriptor = { _class: "ui-codeblock", _data: { source, language: "html" } };
  const markdownDescriptor = { _class: "ui-markdown", _data: { source: `**Status** ${label}` } };
  const card = Card.create({ _class: "ui-card", _data: { label: "Details" }, _children: [
    buttonDescriptor,
    { _class: "ui-card", _children: [fieldDescriptor, markdownDescriptor, codeDescriptor, buttonDescriptor] },
  ] });
  const [button, subcard] = card.children;
  const [field, markdown, code, secondButton] = subcard.children;
  let clicks = 0;
  button.addEventListener("click", () => clicks++);
  document.body.append(card);
  try {
    check(card.getAttribute("aria-label") === "Details", "card owns its label");
    check(button instanceof Button && subcard instanceof Card && field instanceof Field && markdown instanceof Markdown
      && code instanceof CodeBlock && secondButton instanceof Button && secondButton !== button, "ordered recursive fresh elements");
    check(button.control.textContent === label && !card.querySelector("img, script"), "text/source stayed content, not markup");
    check(markdown.querySelector("strong")?.textContent === "Status" && code.querySelector("code")?.textContent === source, "widget-specific renderers handled data");
    check(field.control.labels[0].textContent === "Name" && field.control.required && field.control.value === "Ada", "field owns native controls/data");
    button.control.click();
    check(clicks === 1 && executed === 0 && !button.control.disabled && !button.hasAttribute("id") && !button.hasAttribute("title"), "callbacks and arbitrary data were not reflected or called");
    const named = Button.create({ _data: { text: "Save", type: "submit", disabled: true } });
    const generic = createComponent({ _class: "ui-button", _data: { text: "Save", type: "submit", disabled: true } });
    check(named instanceof Button && generic instanceof Button && named.outerHTML === generic.outerHTML,
      "named and generic constructors agree");
  } finally { card.remove(); }

  const selectDescriptor = JSON.parse(JSON.stringify({ _class: "ui-select", _data: {
    label, name: "speed", value: "standard", required: true,
    options: [
      { value: "", label: "Unavailable", disabled: true },
      { value: "standard", label: "Standard" },
      { value: label, label, onclick: "do not reflect" },
      { value: 3, label: "Not a valid row" },
    ],
  } }));
  const select = createComponent(selectDescriptor);
  const another = Select.create({ _data: { label: "Other speeds", disabled: true,
    options: selectDescriptor._data.options, value: "" } });
  const form = document.createElement("form");
  let changes = 0;
  select.addEventListener("change", event => {
    check(event.target === select.control, "change originates at the native control");
    changes++;
  });
  form.append(select, another);
  document.body.append(form);
  try {
    check(select instanceof Select && another instanceof Select && select.control.id !== another.control.id
      && select.control.labels[0].textContent === label && another.control.labels[0].textContent === "Other speeds",
      "each select owns its native accessible name");
    const rows = [...select.control.options];
    check(rows.map(row => row.value).join("|") === `|standard|${label}` && rows[0].disabled
      && rows[2].textContent === label && !rows[2].hasAttribute("onclick") && !form.querySelector("img"),
      "options stay ordered and text-safe; invalid rows are ignored");
    check(select.control.required && select.value === "standard" && new FormData(form).get("speed") === "standard"
      && another.control.disabled && another.control.selectedIndex === 0,
      "native form state and an explicit disabled selection");
    select.focus();
    check(document.activeElement === select.control, "widget focus reaches the native select");
    select.value = label;
    check(select.value === label && new FormData(form).get("speed") === label && changes === 0, "programmatic value is silent");
    select.control.dispatchEvent(new Event("change", { bubbles: true }));
    check(changes === 1, "one native change bubbles through the wrapper");
    form.reset();
    check(select.value === "standard" && changes === 1, "native form reset restores the configured default silently");
    const options = selectDescriptor._data.options.slice(0, 2);
    select.setOptions(options, "unknown");
    check(select.control.selectedIndex === -1 && !form.checkValidity(), "an unmatched value is not silently substituted");
    select.setOptions(options);
    check(select.value === "standard" && changes === 1, "native default skips a disabled row");
  } finally { form.remove(); }
  const rowsWithGetter = [{ get value() { executed++; return "a"; }, label: "A" }];
  Object.defineProperty(rowsWithGetter, "1", { get() { executed++; return { value: "b", label: "B" }; } });
  const skipped = Select.create({ _data: { options: rowsWithGetter } });
  check(executed === 0 && skipped.control.options.length === 0, "descriptor option accessors are not executed");
  rejects(() => Select.create({ _children: [buttonDescriptor] }), /ui-select does not accept _children/);

  rejects(() => createComponent({ _clas: "ui-card" }), /unknown descriptor key _clas/);
  rejects(() => createComponent({ _class: "Button" }), /unknown component tag "Button"/);
  rejects(() => createComponent({ _class: "ui-card", onclick() {} }), /unknown descriptor key onclick/);
  rejects(() => Button.create({ _class: "ui-card" }), /does not match named factory "ui-button"/);
  rejects(() => createComponent({ _class: "ui-card", _children: {} }), /_children must be an array/);
  rejects(() => createComponent({ _class: "ui-card", _children: [{ _class: "ui-butotn" }] }), /_children\[0\].*unknown component tag "ui-butotn"/);
  rejects(() => createComponent({ _class: "ui-card", _children: [,] }), /_children\[0\]/);
  rejects(() => Markdown.create({ _children: [buttonDescriptor] }), /ui-markdown does not accept _children/);
  rejects(() => createComponent({ get _class() { executed++; return "ui-card"; } }), /_class.*not an accessor/);
  const cyclic = { _class: "ui-card", _children: [] };
  cyclic._children.push(cyclic);
  rejects(() => createComponent(cyclic), /cyclic component descriptor/);
  check(executed === 0, "a descriptor getter executed");

  const messageDescriptor = {
    _class: "chat-message", _data: { role: "assistant", text: "**Reply**" },
    _children: [{ _class: "ui-button", _data: { text: "Continue" } }],
  };
  check(customElements.get("chat-message") === ChatMessage, "production element must already be defined");
  rejects(() => createComponent(messageDescriptor), /unknown component tag "chat-message"/);
  const message = ChatMessage.create(messageDescriptor);
  const messageButton = message.querySelector(".message-ui > ui-button");
  check(message instanceof ChatMessage && messageButton instanceof Button && messageButton.textContent === "Continue",
    "private ChatMessage factory nests the public Button in its interactive region");

  class PrivateFixture extends HTMLElement {}
  customElements.define("builder-test-private", PrivateFixture);
  const scope = createComponentRegistry();
  const sibling = createComponentRegistry();
  const createPrivate = scope.register("builder-test-private", PrivateFixture, (node, data, children) => {
    const slot = document.createElement("section");
    slot.className = data.slot;
    slot.append(...children);
    node.append(slot);
  });
  const privateDescriptor = { _class: "builder-test-private", _data: { slot: "owned" }, _children: [buttonDescriptor] };
  const privateElement = scope.create(privateDescriptor);
  check(privateElement instanceof PrivateFixture && privateElement.querySelector(".owned > ui-button") instanceof Button,
    "local registry inherits shared widgets and component owns mounting");
  check(createPrivate(privateDescriptor) instanceof PrivateFixture, "local named factory");
  const publicNodeInPrivateScope = scope.create({ _class: "ui-card", _children: [privateDescriptor] });
  check(publicNodeInPrivateScope.firstElementChild instanceof PrivateFixture, "nested resolution stays in the invoking scope");
  rejects(() => createComponent(privateDescriptor), /unknown component tag "builder-test-private"/);
  rejects(() => sibling.create(privateDescriptor), /unknown component tag "builder-test-private"/);
  rejects(() => scope.register("builder-test-private", PrivateFixture, () => {}), /already registered/);
  rejects(() => scope.register("builder-test-wrong", PrivateFixture, () => {}), /not defined for that component class/);
}
