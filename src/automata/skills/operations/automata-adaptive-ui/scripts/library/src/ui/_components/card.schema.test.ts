import { validateCardData } from "./card.schema.js";

Deno.test("Card schema fills defaults and rejects unknown fields", () => {
  const data = validateCardData({});
  if (data.variant !== "surface" || data.padding !== "md") {
    throw new Error("Card defaults should be applied");
  }

  let rejected = false;
  try {
    validateCardData({ unknown: true });
  } catch {
    rejected = true;
  }
  if (!rejected) {
    throw new Error("Unknown Card data should be rejected");
  }
});
