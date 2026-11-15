import { palette } from "../_tokens/color";
import type { ResolvedTheme } from "../_theme/index";

export const codeBlockStyle = `
  display: block; min-width: 0; max-width: 100%; margin-block: .8rem;
  overflow: hidden; border: 1px solid; border-radius: .6rem;
  font-size: .875rem; line-height: 1.55; white-space: normal;
  & .code-header { display: flex; align-items: center; gap: .65rem; padding: .4rem .65rem; border-bottom: 1px solid; }
  & .code-language { min-width: 0; overflow-wrap: anywhere; font-size: .75rem; }
  & .copy-status { margin-left: auto; font-size: .75rem; }
  & button { flex-shrink: 0; border: 1px solid; border-radius: .35rem; padding: .25rem .6rem; font: inherit; font-size: .75rem; cursor: pointer; }
  & button:focus-visible, & pre:focus-visible { outline: 2px solid; outline-offset: -2px; }
  & pre { display: block; max-width: 100%; overflow-x: auto; margin: 0; padding: .8rem 1rem; white-space: pre; overflow-wrap: normal; tab-size: 4; }
  & code { font-family: ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace; font-size: inherit; line-height: inherit; white-space: inherit; }
`;

export function codeBlockThemeStyle(theme: ResolvedTheme): string {
  const r = theme.roles;
  const shade = theme.mode === "dark" ? 300 : 700;
  return `
    color: ${r.text}; background: ${r.surfaceRaised}; border-color: ${r.border};
    & .code-header { background: ${r.surface}; border-color: ${r.border}; }
    & .code-language, & .copy-status { color: ${r.mutedText}; }
    & button { color: ${r.text}; background: ${r.surfaceRaised}; border-color: ${r.border}; }
    & button:hover { background: ${r.accentSoft}; }
    & button:focus-visible, & pre:focus-visible { outline-color: ${r.focus}; }
    & .hljs-comment, & .hljs-quote { color: ${r.mutedText}; font-style: italic; }
    & .hljs-keyword, & .hljs-selector-tag, & .hljs-literal, & .hljs-doctag { color: ${palette.violet[shade]}; }
    & .hljs-string, & .hljs-regexp, & .hljs-addition, & .hljs-attribute { color: ${palette.green[shade]}; }
    & .hljs-number, & .hljs-symbol, & .hljs-bullet, & .hljs-link { color: ${palette.orange[shade]}; }
    & .hljs-title, & .hljs-section, & .hljs-name, & .hljs-selector-id, & .hljs-selector-class { color: ${palette.blue[shade]}; }
    & .hljs-built_in, & .hljs-type, & .hljs-attr, & .hljs-variable, & .hljs-params, & .hljs-meta { color: ${palette.redViolet[shade]}; }
    & .hljs-deletion { color: ${r.error}; }
    & .hljs-emphasis { font-style: italic; } & .hljs-strong { font-weight: 700; }
  `;
}
