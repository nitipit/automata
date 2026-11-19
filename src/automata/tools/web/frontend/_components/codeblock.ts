import hljs from "highlight.js/lib/core";
import typescript from "highlight.js/lib/languages/typescript";
import javascript from "highlight.js/lib/languages/javascript";
import xml from "highlight.js/lib/languages/xml";
import css from "highlight.js/lib/languages/css";
import json from "highlight.js/lib/languages/json";
import python from "highlight.js/lib/languages/python";
import bash from "highlight.js/lib/languages/bash";
import markdown from "highlight.js/lib/languages/markdown";
import { Base } from "./base";
import type { ResolvedTheme } from "../_theme/index";
import { codeBlockStyle, codeBlockThemeStyle } from "./codeblock.style";
import { registerSharedComponent } from "./create";
import { rejectChildren, stringData } from "./descriptor-data";

type CodeBlockData = { source?: string; language?: string };

// Component-local registry: no automatic detection, page-wide highlighting or plugins.
const highlighter = hljs.newInstance();
for (const [name, grammar] of Object.entries({ typescript, javascript, xml, css, json, python, bash, markdown })) {
  highlighter.registerLanguage(name, grammar);
}

/** Read-only source. Pass code by property, never by interpolating an HTML attribute. */
export class CodeBlock extends Base {
  static get create() { return createCodeBlock; }
  private originalSource = "";
  private requestedLanguage = "";
  private initialized = false;
  private copyAttempt = 0;
  private readonly header = document.createElement("div");
  private readonly label = document.createElement("span");
  private readonly copy = document.createElement("button");
  private readonly feedback = document.createElement("span");
  private readonly pre = document.createElement("pre");
  private readonly code = document.createElement("code");

  constructor() {
    super();
    this.header.className = "code-header";
    this.label.className = "code-language";
    this.copy.type = "button";
    this.copy.textContent = "Copy";
    this.copy.setAttribute("aria-label", "Copy code");
    this.feedback.className = "copy-status";
    this.feedback.setAttribute("role", "status");
    this.feedback.setAttribute("aria-live", "polite");
    this.pre.tabIndex = 0;
    this.pre.setAttribute("aria-label", "Code, horizontally scrollable");
    this.code.className = "hljs";
    this.pre.append(this.code);
    this.header.append(this.label, this.feedback, this.copy);
    this.copy.addEventListener("click", () => { void this.copySource(); });
    this.renderCode();
  }

  connectedCallback(): void {
    super.connectedCallback();
    // Do not append children in the custom-element constructor (createElement contract).
    if (!this.initialized) {
      this.initialized = true;
      this.append(this.header, this.pre);
    }
  }

  get source(): string { return this.originalSource; }
  set source(value: string) { this.setCode(value, this.requestedLanguage); }
  get language(): string { return this.requestedLanguage; }
  set language(value: string) { this.setCode(this.originalSource, value); }

  setCode(source: string, language = ""): void {
    const nextSource = String(source ?? "");
    const nextLanguage = String(language ?? "");
    if (this.originalSource === nextSource && this.requestedLanguage === nextLanguage) return;
    this.originalSource = nextSource;
    this.requestedLanguage = nextLanguage;
    this.copyAttempt++;
    this.feedback.textContent = "";
    this.copy.removeAttribute("aria-busy");
    this.renderCode();
  }

  protected themedStyle(theme: ResolvedTheme): string { return codeBlockThemeStyle(theme); }

  private renderCode(): void {
    const language = this.requestedLanguage.trim().split(/\s+/)[0].toLowerCase();
    const known = !!language && !!highlighter.getLanguage(language);
    this.label.textContent = known ? language : language ? `${language} · plain text` : "Plain text";
    if (known) {
      try {
        // Only the pinned highlighter's escaped output is HTML. Carriage returns are
        // entities so HTML parsing cannot normalize the original source line endings.
        this.code.innerHTML = highlighter.highlight(this.originalSource, { language, ignoreIllegals: true }).value.replace(/\r/g, "&#13;");
        return;
      } catch { /* A grammar failure must still display source, never hide it. */ }
    }
    this.code.textContent = this.originalSource;
  }

  private async copySource(): Promise<void> {
    const attempt = ++this.copyAttempt;
    const source = this.originalSource;
    this.copy.setAttribute("aria-busy", "true");
    this.feedback.textContent = "";
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(source);
      if (attempt === this.copyAttempt) this.feedback.textContent = "Copied";
    } catch {
      if (attempt === this.copyAttempt) this.feedback.textContent = "Copy failed — select code to copy manually";
    } finally {
      if (attempt === this.copyAttempt) this.copy.removeAttribute("aria-busy");
    }
  }
}

CodeBlock.css = codeBlockStyle;
CodeBlock.define("ui-codeblock");
const createCodeBlock = registerSharedComponent("ui-codeblock", CodeBlock,
  (element, data: CodeBlockData | undefined, children) => {
    rejectChildren("ui-codeblock", children);
    element.setCode(stringData(data, "source") ?? "", stringData(data, "language"));
  });
