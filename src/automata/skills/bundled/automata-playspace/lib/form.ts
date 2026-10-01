// @ts-types="./adaptive-ui.d.ts"
import { Base, Form, Button } from "./adaptive-ui.js";
import type { FormProps, FormState, ComponentContext, ComponentDefinition } from "./types.js";
import { ContractError, emit, event, selector } from "./contracts.js";
import { formContracts as contracts } from "./form.schema.js";
import { validateFormHistory } from "./form-history.js";

/** ps-form owns its controls, state, local revision action and event semantics. */
export class FormComponent extends Base<{ props: FormProps; context: ComponentContext }> {
    props: FormProps;
    context: ComponentContext;
    live = false;
    state: FormState;
    form: Form;
    feedback: HTMLParagraphElement;
    summary: HTMLParagraphElement;
    reviseButton: Button;
    controls: HTMLFieldSetElement;
    onInput: () => void;
    onFormSubmit: (event: Event) => void;
    onRevision: () => void;
    static {
      this.css = `
        display: grid; gap: .75rem; min-width: 0;
        .feedback { white-space: pre-wrap; color: var(--aui-danger, #b42318); font-size: .9rem; }
        .submission { font-size: .85rem; overflow-wrap: anywhere; }
        aui-button { justify-self: start; }
        aui-button[hidden] { display: none; }
        .controls { border: 0; margin: 0; padding: 0; min-inline-size: 0; }
      `;
    }
    applyData({ props, context }: { props: FormProps; context: ComponentContext }): void {
      this.props = props;
      this.context = context;
      this.live = true;
      this.state = context.state === undefined ? { values: props.initialValues, submission: null } : contracts.validateState(props, context.state);
      this.id = context.componentId;
      this.form = Form.create({ data: { title: props.title, submitLabel: props.submitLabel, fields: props.fields } });
      this.feedback = document.createElement("p");
      this.feedback.className = "feedback";
      this.feedback.setAttribute("role", "alert");
      this.summary = document.createElement("p");
      this.summary.className = "submission";
      this.reviseButton = Button.create({ data: { label: "Revise in a new copy", type: "button", tone: "primary" } });
      this.reviseButton.hidden = true;
      this.controls = document.createElement("fieldset");
      this.controls.className = "controls";
      this.controls.append(this.form);
      this.append(this.controls, this.summary, this.reviseButton, this.feedback);
      this.restoreValues();
      this.onInput = () => {
        if (!this.live || this.state.submission) return;
        this.state.values = this.readValues();
        context.changed(); // draft only; no transport
      };
      this.onFormSubmit = nativeEvent => {
        nativeEvent.stopPropagation();
        if (!this.live || this.state.submission) return;
        if (!context.canSend()) {
          this.feedback.textContent = "Submission unavailable while disconnected/busy/pending. Values retained; nothing sent.";
          return;
        }
        try {
          const values = this.readValues();
          const submission = contracts.submit(props, values, crypto.randomUUID());
          this.state = { values: submission.values, submission };
          this.showSubmission();
          context.changed();
          emit(this, event("form-submit", selector("ps-form", this.id), submission));
        } catch (error) {
          this.feedback.textContent = error instanceof ContractError ? error.message : "Submission could not complete; no automatic retry. Check connection state.";
        }
      };
      this.onRevision = () => {
        if (!this.live || !this.state.submission) return;
        // Always local. Copy prior full values; original remains immutable.
        context.appendRevision(contracts.revise(props, this.state.submission, this.id));
      };
      this.form.addEventListener("input", this.onInput);
      this.form.addEventListener("aui-form-submit", this.onFormSubmit);
      this.reviseButton.addEventListener("click", this.onRevision);
      this.showSubmission();
    }
    readValues(): Record<string, string> {
      return Object.fromEntries(this.props.fields.map(field => {
        const inputs = [...this.form.querySelectorAll("input")].filter(input => input.name === field.name);
        return [field.name, field.kind === "choice" ? inputs.find(input => input.checked)?.value ?? "" : inputs[0]?.value ?? ""];
      }));
    }
    restoreValues() {
      for (const input of this.form.querySelectorAll("input")) {
        const value = this.state.values[input.name];
        if (input.type === "radio") input.checked = value === input.value;
        else input.value = value ?? "";
      }
    }
    showSubmission() {
      const submission = this.state.submission;
      // Parent fieldset survives catalog Form's connected-time reconciliation.
      this.controls.disabled = Boolean(submission);
      this.reviseButton.hidden = !submission;
      this.summary.textContent = submission ? `Submitted (read-only) · ${submission.submissionId}${submission.previousSubmissionId ? ` · revises ${submission.previousSubmissionId}` : ""}. A correction does not undo external actions.` :
        this.props.revision ? `Revision draft · previous submission ${this.props.revision.previousSubmissionId}. Editing sends nothing.` : "Local draft · editing sends nothing.";
    }
    snapshot(): FormState {
      // Read DOM too, for programmatic edits that did not dispatch input.
      if (!this.state.submission) this.state.values = this.readValues();
      return contracts.validateState(this.props, this.state);
    }
    dispose() {
      this.live = false;
      this.form.removeEventListener("input", this.onInput);
      this.form.removeEventListener("aui-form-submit", this.onFormSubmit);
      this.reviseButton.removeEventListener("click", this.onRevision);
    }
}

export const formDefinition: ComponentDefinition = {
  contract: contracts.pointer,
  validate: contracts.validateProps,
  validateState: contracts.validateState,
  validateHistory: validateFormHistory,
  events: {
    "form-submit"(detail, instance) {
      const submission = contracts.validateSubmission(instance.props, detail);
      const recorded = instance.state?.submission;
      if (!recorded || JSON.stringify(recorded) !== JSON.stringify(submission)) {
        throw new ContractError(contracts.pointer, { detail: "Submission must match the emitting readonly component state" });
      }
      return submission;
    },
  },
  create(props, context) {
    validateFormHistory(context.history);
    const element = FormComponent.create({ data: { props, context } });
    return { element, snapshot: () => element.snapshot(), dispose: () => element.dispose() };
  },
};
