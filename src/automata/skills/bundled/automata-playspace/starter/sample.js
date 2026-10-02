import { component, text, json } from "./lib/playspace.js";
/** Local demonstration only; each rendered component gets a fresh stable ID. */
export function sampleForm() {
  return component("ps-form", {
    title: "Plan a small experiment", submitLabel: "Submit complete answers",
    fields: [
      { name: "goal", kind: "text", label: "What would you like to explore?", required: true, minLength: 2, maxLength: 240 },
      { name: "pace", kind: "choice", label: "How should we approach it?", required: true,
        choices: [{ value: "quick", label: "Quick sketch" }, { value: "careful", label: "Careful comparison" }] },
      { name: "notes", kind: "text", label: "Anything else? (optional)", required: false, maxLength: 500 },
    ],
  });
}
export function sampleReply(payload) {
  if (payload.type === "component" && payload.data.name === "ps-text") {
    const value = payload.data.props.text;
    if (/form|plan|experiment/i.test(value)) return sampleForm();
    if (/json/i.test(value)) return json({ sample: true, note: "Literal data, not executable source", suggestions: ["Try a form", "Revise after submission"] });
    return text(`Sample agent (local, not live): ${value}\n\nTry “form” or “json”.`);
  }
  if (payload.type === "event" && payload.data.name === "form-submit") {
    return text(`Sample agent: received complete answers locally${payload.data.detail.previousSubmissionId ? " as an explicit correction" : ""}. No external action performed. Revise opens a prefilled copy; editing sends nothing.`);
  }
  return text("Sample agent: payload received locally. No external action performed.");
}
