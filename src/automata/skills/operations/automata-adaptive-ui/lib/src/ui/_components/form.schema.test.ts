import { validateFormData } from "./form.schema.ts";

Deno.test("Form schema accepts choice/text fields and defaults", () => {
  const data = validateFormData({
    title: "Choose",
    fields: [
      {
        name: "choice",
        kind: "choice",
        label: "Choice",
        required: true,
        choices: [{ value: "a", label: "A" }],
      },
      { name: "note", kind: "text", label: "Note", required: false },
    ],
  });
  if (data.submitLabel !== "Submit" || data.fields.length !== 2) {
    throw new Error("Form defaults or fields are incorrect");
  }
});

Deno.test("Form schema rejects duplicate names and invalid bounds", () => {
  for (const fields of [
    [
      { name: "same", kind: "text", label: "One", required: false },
      { name: "same", kind: "text", label: "Two", required: false },
    ],
    [{ name: "note", kind: "text", label: "Note", required: false, minLength: 5, maxLength: 2 }],
  ]) {
    let rejected = false;
    try {
      validateFormData({ fields });
    } catch {
      rejected = true;
    }
    if (!rejected) throw new Error("Invalid Form data was accepted");
  }
});
