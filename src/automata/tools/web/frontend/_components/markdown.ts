import MarkdownIt from "markdown-it";
import type { Env, RendererRule } from "markdown-it";
import { Base } from "./base";
import { CodeBlock } from "./codeblock";
import type { ResolvedTheme, ThemeRef } from "../_theme/index";
import { markdownStyle, markdownThemeStyle } from "./markdown.style";
import { registerSharedComponent } from "./create";
import { rejectChildren, stringData } from "./descriptor-data";

type MarkdownData = { source?: string };

type Fence = { key: string; source: string; language: string };
type RenderEnv = Env & { codeBlocks: Fence[] };
const parser = new MarkdownIt({ html: false, linkify: false, typographer: false });
const defaultValidateLink = parser.validateLink.bind(parser);
parser.validateLink = (url: string): boolean => {
  if (!defaultValidateLink(url) || /[\u0000-\u0020\u007f]/.test(url)) return false;
  const scheme = /^([a-z][a-z\d+.-]*):/i.exec(url)?.[1].toLowerCase();
  return !scheme || ["http", "https", "mailto"].includes(scheme);
};
const renderCode: RendererRule = (tokens, index, _options, environment) => {
  const token = tokens[index];
  const env = environment as RenderEnv;
  const slot = env.codeBlocks.length;
  env.codeBlocks.push({
    key: `${token.type}:${token.map?.[0] ?? index}`,
    source: token.content,
    language: token.type === "fence" ? token.info.trim().split(/\s+/)[0] : "",
  });
  // Only a renderer-generated integer enters markup. Source is a property later.
  return `<ui-codeblock data-md-code="${slot}"></ui-codeblock>\n`;
};
parser.renderer.rules.fence = renderCode;
parser.renderer.rules.code_block = renderCode;

function sameShape(existing: Node | null, desired: Node): boolean {
  if (!existing || existing.nodeType !== desired.nodeType) return false;
  if (existing instanceof Element && desired instanceof Element) {
    return existing.localName === desired.localName && existing.namespaceURI === desired.namespaceURI && existing.localName !== "ui-codeblock";
  }
  return true;
}

/** Shared safe Markdown for assistant text and generated UI. No raw HTML/plugins. */
export class Markdown extends Base {
  static get create() { return createMarkdown; }
  private originalSource = "";
  private blocks = new Map<string, CodeBlock>();
  private codeTheme?: ThemeRef;

  override get theme(): ThemeRef { return super.theme; }
  override set theme(reference: ThemeRef | undefined) {
    super.theme = reference;
    this.codeTheme = reference;
    for (const block of this.blocks.values()) block.theme = reference;
  }

  get source(): string { return this.originalSource; }
  set source(value: string) {
    const source = String(value ?? "");
    if (source === this.originalSource) return;
    const env: RenderEnv = { codeBlocks: [] };
    const template = document.createElement("template");
    // This is ONLY Markdown-it output with html:false, a fixed URL policy and
    // internal integer fence placeholders. No input HTML/source attributes enter.
    template.innerHTML = parser.render(source, env);
    const nextBlocks = new Map<string, CodeBlock>();
    const root = this.getRootNode() as Document | ShadowRoot;
    const active = root.activeElement;
    const focused = active instanceof HTMLElement && this.contains(active) ? active : undefined;
    this.reconcile(this, template.content, env.codeBlocks, nextBlocks);
    this.blocks = nextBlocks;
    this.originalSource = source;
    if (focused?.isConnected && root.activeElement !== focused) focused.focus({ preventScroll: true });
  }

  protected themedStyle(theme: ResolvedTheme): string { return markdownThemeStyle(theme); }

  private reconcile(parent: Node, desired: Node, fences: Fence[], nextBlocks: Map<string, CodeBlock>): void {
    let cursor = parent.firstChild;
    for (const target of [...desired.childNodes]) {
      let node: Node;
      if (target instanceof Element && target.localName === "ui-codeblock") {
        const fence = fences[Number(target.getAttribute("data-md-code"))];
        let block = this.blocks.get(fence.key);
        if (!block) {
          block = new CodeBlock();
          block.theme = this.codeTheme;
        }
        block.setCode(fence.source, fence.language);
        nextBlocks.set(fence.key, block);
        node = block;
        if (cursor !== node) parent.insertBefore(node, cursor);
      } else {
        node = sameShape(cursor, target) ? cursor! : target.cloneNode(false);
        if (node !== cursor) parent.insertBefore(node, cursor);
        if (node instanceof Element && target instanceof Element) {
          for (const attribute of [...node.attributes]) {
            if (!target.hasAttribute(attribute.name)) node.removeAttribute(attribute.name);
          }
          for (const attribute of [...target.attributes]) {
            if (node.getAttribute(attribute.name) !== attribute.value) node.setAttribute(attribute.name, attribute.value);
          }
          this.reconcile(node, target, fences, nextBlocks);
        } else if (node.nodeValue !== target.nodeValue) node.nodeValue = target.nodeValue;
      }
      cursor = node.nextSibling;
    }
    while (cursor) {
      const next = cursor.nextSibling;
      parent.removeChild(cursor);
      cursor = next;
    }
  }
}

Markdown.css = markdownStyle;
Markdown.define("ui-markdown");
const createMarkdown = registerSharedComponent("ui-markdown", Markdown,
  (element, data: MarkdownData | undefined, children) => {
    rejectChildren("ui-markdown", children);
    element.source = stringData(data, "source") ?? "";
  });
