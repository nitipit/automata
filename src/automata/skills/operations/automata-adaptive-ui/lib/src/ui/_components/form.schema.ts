import { defineField, Model } from "../_lib/edictor.bundle.js";

export type FormChoice = { value: string; label: string };
export type FormField =
  | {
      name: string;
      kind: "choice";
      label: string;
      required: boolean;
      choices: FormChoice[];
    }
  | {
      name: string;
      kind: "text";
      label: string;
      required: boolean;
      minLength?: number;
      maxLength?: number;
    };

export type FormData = {
  title?: string;
  submitLabel: string;
  fields: FormField[];
};

class FormDataModel extends Model {}

FormDataModel.define({
  title: defineField({ initial: "" })
    .instance("string")
    .assert((value: unknown) => typeof value === "string", "Form title must be text"),
  submitLabel: defineField({ initial: "Submit" })
    .instance("string")
    .assert(
      (value: unknown) => typeof value === "string" && value.trim().length > 0,
      "Form submit label is required",
    ),
  fields: defineField({ required: true })
    .assert(Array.isArray, "Form fields are required")
    .assert((value: unknown) => (value as unknown[]).length > 0, "Form needs one field"),
});

/**
 * Validates only catalog/rendering data. Form question/answer semantics belong
 * to the optional channel Form adapter, so this component stays useful alone.
 */
export function validateFormData(data: unknown): FormData {
  const base = FormDataModel.validate(data ?? {}) as Omit<FormData, "fields"> & { fields: unknown[] };
  const fields = base.fields.map(validateField);
  const names = new Set<string>();
  for (const field of fields) {
    if (names.has(field.name)) throw new Error(`Duplicate Form field: ${field.name}`);
    names.add(field.name);
  }
  return { title: base.title || undefined, submitLabel: base.submitLabel, fields };
}

function validateField(value: unknown): FormField {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Form field must be an object");
  }
  const field = value as Record<string, unknown>;
  if (
    typeof field.name !== "string" || !field.name.trim() ||
    typeof field.label !== "string" || !field.label.trim() ||
    typeof field.required !== "boolean"
  ) {
    throw new Error("Form field identity, label, and required flag are required");
  }
  if (field.kind === "choice") {
    if (!Array.isArray(field.choices) || field.choices.length === 0) {
      throw new Error(`Choices are required for ${field.name}`);
    }
    const choices = field.choices.map((choice) => {
      if (!choice || typeof choice !== "object" || Array.isArray(choice)) {
        throw new Error(`Choice is invalid for ${field.name}`);
      }
      const item = choice as Record<string, unknown>;
      if (typeof item.value !== "string" || !item.value || typeof item.label !== "string" || !item.label.trim()) {
        throw new Error(`Choice value and label are required for ${field.name}`);
      }
      return { value: item.value, label: item.label };
    });
    return {
      name: field.name,
      kind: "choice",
      label: field.label,
      required: field.required,
      choices,
    };
  }
  if (field.kind === "text") {
    const rawMinLength = field.minLength;
    const rawMaxLength = field.maxLength;
    const minLength = rawMinLength === undefined ? undefined :
      typeof rawMinLength === "number" ? rawMinLength : Number.NaN;
    const maxLength = rawMaxLength === undefined ? undefined :
      typeof rawMaxLength === "number" ? rawMaxLength : Number.NaN;
    if (minLength !== undefined && (!Number.isInteger(minLength) || minLength < 0)) {
      throw new Error(`Minimum text length is invalid for ${field.name}`);
    }
    if (maxLength !== undefined && (!Number.isInteger(maxLength) || maxLength < 0)) {
      throw new Error(`Maximum text length is invalid for ${field.name}`);
    }
    if (minLength !== undefined && maxLength !== undefined && minLength > maxLength) {
      throw new Error(`Text bounds are invalid for ${field.name}`);
    }
    return {
      name: field.name,
      kind: "text",
      label: field.label,
      required: field.required,
      ...(minLength === undefined ? {} : { minLength }),
      ...(maxLength === undefined ? {} : { maxLength }),
    };
  }
  throw new Error(`Unsupported Form field kind for ${field.name}`);
}
