import { defineField, Model } from "../_lib/edictor.bundle.js";

export type CardData = {
  variant: "surface" | "outlined";
  padding: "sm" | "md" | "lg";
};

class CardDataModel extends Model {}

CardDataModel.define({
  variant: defineField({ initial: "surface" })
    .instance("string")
    .assert(
      (value: unknown) => value === "surface" || value === "outlined",
      "Unsupported card variant",
    ),
  padding: defineField({ initial: "md" })
    .instance("string")
    .assert(
      (value: unknown) => value === "sm" || value === "md" || value === "lg",
      "Unsupported card padding",
    ),
});

/** Validates Card attributes and fills the component's defaults. */
export function validateCardData(data: unknown): CardData {
  return CardDataModel.validate(data ?? {}) as CardData;
}
