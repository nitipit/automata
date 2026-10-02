/** Starter envelope + linked submission integrity, separate from catalog Chat. */
export function validateStarterSnapshot(value, { validateChatSnapshot, ChatContractError }, registry, contracts) {
  const fail = hint => { throw new ChatContractError("PlayspaceChatSnapshot v1 {version:1,mode:'sample'|'live',chat:ChatSnapshot}", { snapshot: hint }); };
  if (!value || typeof value !== "object" || Array.isArray(value) ||
    Object.keys(value).some(key => !["version", "mode", "chat"].includes(key)) ||
    value.version !== 1 || !["sample", "live"].includes(value.mode)) fail("Unsupported/malformed starter envelope");
  const chat = validateChatSnapshot(value.chat, registry);
  const forms = chat.messages.filter(message => message.content.type === "component" && message.content.data.name === "form");
  const submissions = new Map();
  for (const message of forms) {
    const submission = chat.componentStates[message.id]?.submission;
    if (submission) {
      if (submission.messageId !== message.id || submissions.has(submission.id)) fail("Submission IDs must be unique and match their component messages");
      submissions.set(submission.id, submission);
    }
  }
  for (const message of forms) {
    const props = message.content.data.props;
    if (props.revision) {
      const previous = submissions.get(props.revision.previousSubmissionId);
      const origin = forms.find(form => form.id === props.revision.originMessageId);
      if (!previous || !origin || previous.originMessageId !== origin.id || origin.content.data.props.revision !== null ||
        chat.messages.indexOf(message) <= chat.messages.findIndex(item => item.id === previous.messageId)) fail("Revision must link a prior submission and original Form message");
      if (props.fields.some(field => props.initialValues[field.name] !== previous.values[field.name])) fail("Revision copy must begin with prior complete values");
    }
  }
  for (const message of chat.messages) {
    if (message.role !== "user" || message.content.type !== "json" || message.content.data?.kind !== "form-submission") continue;
    const { kind: _kind, ...data } = message.content.data;
    const original = submissions.get(data.id);
    const form = forms.find(form => form.id === data.messageId);
    if (!original || !form) fail("Submission display message must link a readonly component state");
    const valid = contracts.validateSubmission(form.content.data.props, data);
    if (Object.keys(original).some(key => key !== "values" && original[key] !== valid[key]) ||
      form.content.data.props.fields.some(field => original.values[field.name] !== valid.values[field.name])) fail("Submission display and component state must agree");
  }
  return { version: 1, mode: value.mode, chat };
}
