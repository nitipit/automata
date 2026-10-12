/** Page-local example responses; no backend or component configuration schema. */
export function mountComponentExamples(): void {
  const button = document.querySelector("#example-button");
  const result = document.querySelector("#button-result");
  button?.addEventListener("click", () => { if (result) result.textContent = "Hello!"; });
  document.querySelector("#example-form")?.addEventListener("aui-form-submit", (event) => {
    const output = document.querySelector("#form-result");
    if (output) output.textContent = JSON.stringify((event as CustomEvent).detail.values, null, 2);
  });
}
