/** Canonical trusted Form models. Import this module in browser and agent checks.
 * Dependency injection shares the catalog's one Edictor instance (no runtime fetch).
 */
export function createFormContracts({ Model, defineField, testChatModel, ChatContractError, cloneChatJSON }) {
  const pointer = "automata-playspace/starter/contracts.js: FormProps / validateAnswers";
  const text = () => defineField({ required: true }).assert(v => typeof v === "string", "Expected text");
  const nonempty = () => text().assert(v => typeof v === "string" && !!v.trim(), "Required text");
  class ChoiceModel extends Model {}
  ChoiceModel.define({ value: nonempty(), label: nonempty() });
  class TextFieldModel extends Model {}
  TextFieldModel.define({
    name: nonempty(), label: nonempty(), kind: text().assert(v => v === "text", "Expected text kind"),
    required: defineField({ required: true }).assert(v => typeof v === "boolean", "Expected boolean"),
    minLength: defineField().assert(v => Number.isInteger(v) && v >= 0, "Nonnegative integer"),
    maxLength: defineField().assert(v => Number.isInteger(v) && v >= 0, "Nonnegative integer"),
  });
  class ChoiceFieldModel extends Model {}
  ChoiceFieldModel.define({
    name: nonempty(), label: nonempty(), kind: text().assert(v => v === "choice", "Expected choice kind"),
    required: defineField({ required: true }).assert(v => typeof v === "boolean", "Expected boolean"),
    choices: defineField({ required: true }).assert(v => Array.isArray(v) && v.length > 0, "Nonempty choices"),
  });
  class RevisionModel extends Model {}
  RevisionModel.define({ originMessageId: nonempty(), previousSubmissionId: nonempty() });
  class FormPropsModel extends Model {}
  FormPropsModel.define({
    title: defineField({ initial: "Form" }).assert(v => typeof v === "string", "Expected text"),
    submitLabel: defineField({ initial: "Submit answers" }).assert(v => typeof v === "string" && !!v.trim(), "Required label"),
    fields: defineField({ required: true }).assert(v => Array.isArray(v) && v.length > 0, "Nonempty fields"),
    initialValues: defineField({ initial: {} }), revision: defineField({ initial: null }),
  });
  const fieldHints = { name: "Unique safe field name", label: "Required text label", kind: "text or choice",
    required: "Boolean required flag", choices: "Nonempty unique choices", minLength: "Nonnegative integer",
    maxLength: "Nonnegative integer >= minLength" };
  const fail = (field, hint) => { throw new ChatContractError(pointer, { [field]: hint }); };
  const test = (model, value, hints) => testChatModel(model, value, pointer, hints);
  function validateProps(value) {
    const base = test(FormPropsModel, value, { title: "Text title", submitLabel: "Nonempty text", fields: "Nonempty fields",
      initialValues: "Partial field/string draft", revision: "null or {originMessageId,previousSubmissionId}" });
    const names = new Set();
    const fields = base.fields.map((raw, index) => {
      const field = test(raw?.kind === "choice" ? ChoiceFieldModel : TextFieldModel, raw, fieldHints);
      if (!/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(field.name) || ["constructor", "prototype"].includes(field.name) || names.has(field.name)) {
        fail(`fields[${index}].name`, "Unique safe name matching [a-zA-Z][a-zA-Z0-9_-]*");
      }
      names.add(field.name);
      if (field.kind === "choice") {
        const choices = field.choices.map(choice => test(ChoiceModel, choice, { value: "Nonempty text", label: "Nonempty text" }));
        if (new Set(choices.map(choice => choice.value)).size !== choices.length) fail(`fields[${index}].choices`, "Unique choice values");
        return { ...field, choices };
      }
      if (field.minLength !== undefined && field.maxLength !== undefined && field.minLength > field.maxLength) fail(`fields[${index}]`, "minLength <= maxLength");
      // Edictor .test includes undefined optional fields; explicitly omit for JSON.
      return Object.fromEntries(Object.entries(field).filter(([, v]) => v !== undefined));
    });
    const props = { ...base, fields };
    props.initialValues = validateDraft(props, base.initialValues);
    props.revision = base.revision === null ? null : test(RevisionModel, base.revision, {
      originMessageId: "Required original component message ID", previousSubmissionId: "Required previous submission ID",
    });
    return cloneChatJSON(props);
  }
  function validateDraft(props, value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) fail("values", "Field/string map required");
    const pairs = Object.entries(value).map(([name, answer]) => {
      const field = props.fields.find(field => field.name === name);
      if (!field || typeof answer !== "string") fail("values", "Only declared fields with string values");
      if (field.kind === "choice" && answer && !field.choices.some(choice => choice.value === answer)) fail(`values.${name}`, "Offered choice value required");
      return [name, answer];
    });
    return Object.fromEntries(pairs);
  }
  /** Complete answers, not a patch: all fields including optional blanks required. */
  function validateAnswers(props, value) {
    const values = validateDraft(props, value);
    class AnswersModel extends Model {}
    const definitions = Object.fromEntries(props.fields.map(field => [field.name,
      text().assert(answer => {
        if (typeof answer !== "string") return false;
        if (field.required && !answer.trim()) return false;
        if (field.kind === "choice") return !answer && !field.required || field.choices.some(choice => choice.value === answer);
        return (!answer && !field.required) ||
          (answer.length >= (field.minLength ?? 0) && answer.length <= (field.maxLength ?? Infinity));
      }, "Answer must meet field contract"),
    ]));
    AnswersModel.define(definitions);
    return test(AnswersModel, values, Object.fromEntries(props.fields.map(field => [field.name,
      field.kind === "choice" ? "Select an offered choice; include optional blanks" :
        `Complete text answer; required=${field.required}, length=${field.minLength ?? 0}..${field.maxLength ?? "unbounded"}`,
    ])));
  }
  class SubmissionModel extends Model {}
  SubmissionModel.define({ id: nonempty(), componentName: text().assert(v => v === "form", "Expected form"),
    messageId: nonempty(), originMessageId: nonempty(), previousSubmissionId: defineField({ required: true }).assert(v => v === null || typeof v === "string" && !!v, "null or ID"), values: defineField({ required: true }),
  });
  function validateSubmission(props, value) {
    const submission = test(SubmissionModel, value, { id: "Required local ID", componentName: "form", messageId: "Originating message ID",
      originMessageId: "Original component message ID", previousSubmissionId: "null or previous submission ID", values: "Complete validated answers" });
    const expected = props.revision;
    if (submission.previousSubmissionId !== (expected?.previousSubmissionId ?? null) ||
      submission.originMessageId !== (expected?.originMessageId ?? submission.messageId)) fail("submission", "Revision links must match component props");
    return { ...submission, values: validateAnswers(props, submission.values) };
  }
  function validateState(props, value) {
    if (!value || typeof value !== "object" || Array.isArray(value) ||
      Object.keys(value).some(key => !["values", "submission"].includes(key))) fail("state", "{values,submission:null|Submission}");
    const values = validateDraft(props, value.values);
    const submission = value.submission === null ? null : validateSubmission(props, value.submission);
    if (submission && JSON.stringify(values) !== JSON.stringify(submission.values)) {
      if (props.fields.some(field => values[field.name] !== submission.values[field.name])) fail("state.values", "Submitted answers are read-only");
    }
    return cloneChatJSON({ values, submission });
  }
  function submit(props, messageId, values, id) {
    return validateSubmission(props, { id, componentName: "form", messageId,
      originMessageId: props.revision?.originMessageId ?? messageId,
      previousSubmissionId: props.revision?.previousSubmissionId ?? null, values });
  }
  function revise(props, submission) {
    const previous = validateSubmission(props, submission);
    return validateProps({ ...props, initialValues: previous.values,
      revision: { originMessageId: previous.originMessageId, previousSubmissionId: previous.id } });
  }
  return { pointer, FormPropsModel, validateProps, validateDraft, validateAnswers, validateSubmission, validateState, submit, revise };
}
