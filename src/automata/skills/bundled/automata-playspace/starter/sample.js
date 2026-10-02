/** Local demonstration, never a live agent or external effect. */
export const sampleForm = { type: "component", data: { name: "form", props: {
  title: "Plan a small experiment", submitLabel: "Submit complete answers",
  fields: [
    { name: "goal", kind: "text", label: "What would you like to explore?", required: true, minLength: 2, maxLength: 240 },
    { name: "pace", kind: "choice", label: "How should we approach it?", required: true,
      choices: [{ value: "quick", label: "Quick sketch" }, { value: "careful", label: "Careful comparison" }] },
    { name: "notes", kind: "text", label: "Anything else? (optional)", required: false, maxLength: 500 },
  ],
} } };
export function sampleReply(content) {
  if (content.type === "text") {
    if (/form|plan|experiment/i.test(content.data)) return sampleForm;
    if (/json/i.test(content.data)) return { type: "json", data: { sample: true, note: "Literal structured data, not executable source", suggestions: ["Try a form", "Revise after submission"] } };
    return { type: "text", data: `Sample agent (local, not live): ${content.data}\n\nTry “form” for an interactive draft or “json” for structured data.` };
  }
  if (content.type === "json" && content.data?.kind === "form-submission") {
    return { type: "text", data: `Sample agent: received complete answers locally${content.data.previousSubmissionId ? " as an explicit correction" : ""}. No external action was performed. Use Revise to open a prefilled copy; editing alone sends nothing.` };
  }
  return { type: "text", data: "Sample agent: content received locally. No external action was performed." };
}
