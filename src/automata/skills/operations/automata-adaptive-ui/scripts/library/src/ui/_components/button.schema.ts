import { defineField, Model } from "../_lib/edictor.bundle.js";

export type ButtonData = {
  label: string;
  tone: "primary" | "danger";
  type: "button" | "submit";
};

class ButtonDataModel extends Model {}

ButtonDataModel.define({
  label: defineField({ required: true })
    .instance("string")
    .assert(
      (value: unknown) => typeof value === "string" && value.trim().length > 0,
      "Button label is required",
    ),
  tone: defineField({ initial: "primary" })
    .instance("string")
    .assert(
      (value: unknown) => value === "primary" || value === "danger",
      "Unsupported button tone",
    ),
  type: defineField({ initial: "button" })
    .instance("string")
    .assert(
      (value: unknown) => value === "button" || value === "submit",
      "Unsupported button type",
    ),
});

/** Validates Button attributes and fills the component's defaults. */
export function validateButtonData(data: unknown): ButtonData {
  return ButtonDataModel.validate(data ?? {}) as ButtonData;
}
