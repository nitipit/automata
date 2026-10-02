import { ContractError } from "./contracts.js";
import { formContracts } from "./form.schema.js";
import type { History, Message, FormProps, FormState, Submission } from "./types.js";

/** Cross-instance integrity runs before ANY candidate Form construction/mount. */
export function validateFormHistory(history: History): void {
  const fail = hint => { throw new ContractError(formContracts.pointer, { revision: hint }); };
  const forms = history.messages.filter(message => message.content.data.name === "ps-form");
  const submissions = new Map<string, { submission: Submission; message: Message }>();
  const byId = new Map(forms.map(message => [message.content.data.id, message]));
  for (const message of forms) {
    const { id, props } = message.content.data;
    const state = history.componentStates[id] as FormState;
    if (!state?.submission) continue;
    const submission = formContracts.validateState(props as FormProps, state).submission;
    if (submissions.has(submission.submissionId)) fail("Submission IDs must be unique");
    submissions.set(submission.submissionId, { submission, message });
  }
  for (const message of forms) {
    const props = message.content.data.props as FormProps;
    if (!props.revision) continue;
    const prior = submissions.get(props.revision.previousSubmissionId);
    const origin = byId.get(props.revision.originComponentId);
    if (!prior || !origin || (origin.content.data.props as FormProps).revision !== null ||
      ((prior.message.content.data.props as FormProps).revision?.originComponentId ?? prior.message.content.data.id) !== origin.content.data.id ||
      history.messages.indexOf(message) <= history.messages.indexOf(prior.message)) {
      fail("Revision must link a prior readonly submission and original Form component");
    }
    if (JSON.stringify(props.fields) !== JSON.stringify((prior.message.content.data.props as FormProps).fields) ||
      props.fields.some(field => props.initialValues[field.name] !== prior.submission.values[field.name]) ||
      Object.keys(props.initialValues).length !== props.fields.length) {
      fail("Revision copy must preserve the prior field contract and complete answers");
    }
  }
}
