import { validateButtonData } from "./button.schema.js";

Deno.test("Button schema requires a label and fills defaults", () => {
  const data = validateButtonData({ label: "Save" });
  if (data.tone !== "primary" || data.type !== "button" || data.disabled !== false) {
    throw new Error("Button defaults should be applied");
  }

  let rejected = false;
  try {
    validateButtonData({ label: " " });
  } catch {
    rejected = true;
  }
  if (!rejected) {
    throw new Error("Blank Button labels should be rejected");
  }
});

Deno.test("Button disabled accepts booleans only", () => {
  if (!validateButtonData({ label: "Save", disabled: true }).disabled) {
    throw new Error("Explicit disabled data was lost");
  }
  for (const disabled of ["false", "true", 0, 1, null]) {
    let rejected = false;
    try { validateButtonData({ label: "Save", disabled }); } catch { rejected = true; }
    if (!rejected) throw new Error(`Non-boolean disabled accepted: ${disabled}`);
  }
});
