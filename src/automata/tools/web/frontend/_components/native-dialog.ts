import { Adapter } from "@devcapsule/adapter";
import { nativeDialogStyle } from "./native-dialog.style";

/** A single native RPC interaction. Undefined is cancellation, never an implicit yes. */
export type DialogRequest =
  | { kind: "confirm"; title: string; message?: string }
  | { kind: "select"; title: string; message?: string; options: string[] }
  | { kind: "input"; title: string; message?: string; placeholder?: string; value?: string }
  | { kind: "editor"; title: string; message?: string; value?: string };

export type DialogResult = boolean | string | undefined;

/** Presentation only: callers own RPC correlation, timeout and cancellation. */
export class NativeDialog extends Adapter {
  private dialog: HTMLDialogElement;
  private resolve?: (value: DialogResult) => void;

  constructor() {
    super();
    this.dialog = document.createElement("dialog");
    this.dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      this.finish(undefined);
    });
  }

  connectedCallback(): void {
    super.connectedCallback();
    if (!this.dialog.isConnected) this.append(this.dialog);
  }

  ask(request: DialogRequest): Promise<DialogResult> {
    if (this.resolve) return Promise.reject(new Error("A dialog is already open"));
    const form = document.createElement("form");
    form.method = "dialog";
    const heading = document.createElement("h2");
    heading.textContent = request.title;
    heading.id = "native-dialog-heading";
    this.dialog.setAttribute("aria-labelledby", heading.id);
    form.append(heading);
    if (request.message) {
      const description = document.createElement("p");
      description.textContent = request.message;
      form.append(description);
    }

    let field: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | undefined;
    if (request.kind === "select") {
      const select = document.createElement("select");
      select.setAttribute("aria-label", request.title);
      for (const option of request.options) {
        const element = document.createElement("option");
        element.value = option;
        element.textContent = option;
        select.append(element);
      }
      field = select;
    } else if (request.kind === "input" || request.kind === "editor") {
      field = document.createElement(request.kind === "editor" ? "textarea" : "input");
      field.setAttribute("aria-label", request.title);
      field.value = request.value ?? "";
      if (request.kind === "input" && request.placeholder) field.setAttribute("placeholder", request.placeholder);
    }
    if (field) form.append(field);

    const actions = document.createElement("div");
    actions.className = "dialog-actions";
    const stop = document.createElement("button");
    stop.type = "button";
    stop.textContent = "Stop";
    stop.addEventListener("click", () => {
      stop.disabled = true;
      this.dispatchEvent(new CustomEvent("stop-request", { bubbles: true }));
    });
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = request.kind === "confirm" ? "No" : "Cancel";
    cancel.addEventListener("click", () => this.finish(request.kind === "confirm" ? false : undefined));
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.textContent = request.kind === "confirm" ? "Yes" : "OK";
    if (request.kind === "select" && request.options.length === 0) submit.disabled = true;
    actions.append(stop, cancel, submit);
    form.append(actions);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      this.finish(request.kind === "confirm" ? true : field?.value);
    });
    this.dialog.replaceChildren(form);
    return new Promise((resolve, reject) => {
      this.resolve = resolve;
      try {
        this.dialog.showModal();
        (field ?? cancel).focus();
      } catch (error) {
        this.resolve = undefined;
        reject(error);
      }
    });
  }

  cancel(): void { this.finish(undefined); }

  disconnectedCallback(): void { this.cancel(); }

  private finish(value: DialogResult): void {
    const resolve = this.resolve;
    if (!resolve) return;
    this.resolve = undefined;
    if (this.dialog.open) this.dialog.close();
    resolve(value);
  }
}

NativeDialog.css = nativeDialogStyle;
NativeDialog.define("native-rpc-dialog");
