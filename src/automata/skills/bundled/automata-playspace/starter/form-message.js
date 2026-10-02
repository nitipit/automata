/** Trusted interactive definition, built from catalog Base/Form/Button. */
export function createFormRegistry(ui, contracts, { canSubmit, onSubmit, onRevise, tagName = "playspace-form-message" }) {
  const { Base, Form, Button, ChatContractError } = ui;
  class FormMessage extends Base {
    static {
      this.css = `
        display: grid; gap: .75rem; min-width: 0;
        .feedback { white-space: pre-wrap; color: var(--aui-danger, #b42318); font-size: .9rem; }
        .submission { font-size: .85rem; overflow-wrap: anywhere; }
        aui-button { justify-self: start; }
        .controls { border: 0; margin: 0; padding: 0; min-inline-size: 0; }
      `;
    }
    applyData({ props, context }) {
      this.props = props;
      this.context = context;
      this.live = true;
      this.state = context.state === undefined ? { values: props.initialValues, submission: null } : contracts.validateState(props, context.state);
      if (this.state.submission && this.state.submission.messageId !== context.messageId) {
        throw new ChatContractError(contracts.pointer, { "submission.messageId": "Must match originating component message" });
      }
      this.form = Form.create({ data: { title: props.title, submitLabel: props.submitLabel, fields: props.fields } });
      this.feedback = document.createElement("p");
      this.feedback.className = "feedback";
      this.feedback.setAttribute("role", "alert");
      this.summary = document.createElement("p");
      this.summary.className = "submission";
      this.reviseButton = Button.create({ data: { label: "Revise in a new copy", type: "button" } });
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
      this.onFormSubmit = event => {
        if (!this.live || this.state.submission) return;
        event.stopPropagation();
        if (!canSubmit()) {
          this.feedback.textContent = "Submission unavailable while disconnected/busy/pending. Values retained; nothing sent.";
          return;
        }
        try {
          const values = this.readValues();
          const submission = contracts.submit(props, context.messageId, values, crypto.randomUUID());
          this.state = { values: submission.values, submission };
          this.showSubmission();
          context.changed();
          onSubmit(submission);
        } catch (error) {
          this.feedback.textContent = error instanceof ChatContractError ? error.message : "Submission could not complete; no automatic retry. Check connection state.";
        }
      };
      this.onRevision = () => {
        if (!this.live || !this.state.submission) return;
        // Always local. Copy prior full values; original remains immutable.
        onRevise(contracts.revise(props, this.state.submission));
      };
      this.form.addEventListener("input", this.onInput);
      this.form.addEventListener("aui-form-submit", this.onFormSubmit);
      this.reviseButton.addEventListener("click", this.onRevision);
      this.showSubmission();
    }
    readValues() {
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
      this.summary.textContent = submission ? `Submitted (read-only) · ${submission.id}${submission.previousSubmissionId ? ` · revises ${submission.previousSubmissionId}` : ""}. A correction does not undo external actions.` :
        this.props.revision ? `Revision draft · previous submission ${this.props.revision.previousSubmissionId}. Editing sends nothing.` : "Local draft · editing sends nothing.";
    }
    snapshot() {
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
  FormMessage.define(tagName);
  return {
    form: {
      contract: contracts.pointer,
      validate: contracts.validateProps,
      validateState: contracts.validateState,
      create(props, context) {
        const element = FormMessage.create({ data: { props, context } });
        return { element, snapshot: () => element.snapshot(), dispose: () => element.dispose() };
      },
    },
  };
}
