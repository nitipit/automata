import type { ResolvedTheme } from "../_theme/index";

export const nativeDialogStyle = `
  & dialog { box-sizing: border-box; width: min(32rem, calc(100vw - 2rem)); border: 1px solid; border-radius: 1rem; padding: 1.5rem; box-shadow: 0 1rem 4rem #0007; }
  & dialog::backdrop { background: #000b; }
  & h2 { margin: 0 0 .75rem; font-size: 1.2rem; }
  & p { margin: 0 0 1rem; white-space: pre-wrap; }
  & input, & select, & textarea { box-sizing: border-box; display: block; width: 100%; padding: .65rem; border: 1px solid; border-radius: .5rem; }
  & textarea { min-height: 12rem; resize: vertical; }
  & .dialog-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: .5rem; margin-top: 1rem; }
  & button { cursor: pointer; border: 1px solid; border-radius: .5rem; padding: .5rem .9rem; }
  & :focus-visible { outline: 3px solid; outline-offset: 2px; }
`;

export function nativeDialogTheme({ roles: r }: ResolvedTheme): string {
  return `
    & dialog, & input, & select, & textarea, & button { color: ${r.text}; background: ${r.surface}; border-color: ${r.border}; }
    & button[type="submit"] { color: ${r.accentText}; background: ${r.accent}; border-color: ${r.accent}; }
    & :focus-visible { outline-color: ${r.focus}; }
  `;
}
