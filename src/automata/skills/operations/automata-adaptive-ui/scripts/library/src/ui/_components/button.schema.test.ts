import { validateButtonData } from "./button.schema.js";

Deno.test("Button schema requires a label and fills defaults", () => {
  const data = validateButtonData({ label: "Save" });
  if (data.tone !== "primary" || data.type !== "button") {
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
