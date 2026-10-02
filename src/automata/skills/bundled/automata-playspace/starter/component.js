/** Authored source is persisted verbatim; validators stay with the component. */
function noteFactory({ Base }, css) {
  const fields = (value, keys) => {
    if (!value || typeof value !== "object" || Array.isArray(value) ||
        Object.keys(value).length !== keys.length ||
        keys.some(key => !Object.hasOwn(value, key))) throw new Error("Invalid fields");
    return value;
  };
  const string = value => {
    if (typeof value !== "string" || value.length > 8000) throw new Error("Bounded text required");
    return value;
  };
  const validateProps = value => ({ title: string(fields(value, ["title"]).title) });
  const validateState = (_props, value) => {
    fields(value, ["draft", "result"]);
    return { draft: string(value.draft), result: string(value.result) };
  };
  class Note extends Base {}
  Note.css = css;
  // The runtime reuses identical definitions; genuinely new evaluations get a
  // distinct tag because browser registrations cannot be undone or overwritten.
  Note.define(`ps-note-${crypto.randomUUID()}`);
  return {
    validateProps, validateState,
    events: {
      request(value) { return { text: string(fields(value, ["text"]).text) }; },
    },
    update(_props, state, value) {
      return { ...state, result: string(fields(value, ["text"]).text) };
    },
    create(props, context) {
      const element = Note.create();
      const form = document.createElement("form");
      const label = document.createElement("label");
      const input = document.createElement("textarea");
      const button = document.createElement("button");
      const heading = document.createElement("h2");
      const output = document.createElement("output");
      heading.textContent = props.title;
      input.id = `${context.id}-draft`;
      input.value = context.state.draft;
      input.maxLength = 8000;
      input.rows = 4;
      label.htmlFor = input.id;
      label.textContent = "Draft (local until Send)";
      button.type = "submit";
      button.textContent = "Send to connected agent";
      output.setAttribute("aria-label", "Agent result");
      output.setAttribute("aria-live", "polite");
      output.textContent = context.state.result;
      const change = () => context.changed();
      const submit = event => {
        event.preventDefault();
        context.emit("request", { text: input.value });
      };
      input.addEventListener("input", change);
      form.addEventListener("submit", submit);
      form.append(label, input, button);
      element.append(heading, form, output);
      return {
        element,
        snapshot: () => ({ draft: input.value, result: output.textContent }),
        dispose() {
          input.removeEventListener("input", change);
          form.removeEventListener("submit", submit);
        },
      };
    },
  };
}
export const starterDefinition = Object.freeze({
  id: "note-v1",
  source: noteFactory.toString(),
  css: `display: block;
    & h2 { margin-top: 0; }
    & form { display: grid; gap: .6rem; }
    & textarea { box-sizing: border-box; width: 100%; font: inherit; }
    & button { justify-self: start; padding: .6rem 1rem; }
    & output { display: block; white-space: pre-wrap; overflow-wrap: anywhere;
      margin-top: 1rem; min-height: 2rem; }`,
});
export function initialSnapshot() {
  return { version: 1, definitions: [{ ...starterDefinition }], layout: [{
    id: "note", definition: starterDefinition.id, props: { title: "Explore one idea" },
    state: { draft: "", result: "" },
  }] };
}
