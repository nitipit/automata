import { color } from "../_tokens/color";

export const nativeDialogStyle = `
  & dialog { width: min(32rem, calc(100vw - 2rem)); border: 1px solid ${color.line}; border-radius: 1rem; padding: 1.5rem; color: ${color.ink}; background: white; box-shadow: 0 1rem 4rem #142b2070; }
  & dialog::backdrop { background: #10251db3; }
  & h2 { margin: 0 0 .75rem; font-size: 1.2rem; }
  & p { margin: 0 0 1rem; white-space: pre-wrap; }
  & input, & select, & textarea { display: block; width: 100%; padding: .65rem; border: 1px solid #a8beb0; border-radius: .5rem; color: ${color.ink}; background: white; }
  & textarea { min-height: 12rem; resize: vertical; }
  & .dialog-actions { display: flex; justify-content: flex-end; gap: .5rem; margin-top: 1rem; }
  & button { cursor: pointer; border: 1px solid ${color.line}; border-radius: .5rem; padding: .5rem .9rem; background: white; color: ${color.ink}; }
  & button[type="submit"] { color: white; background: ${color.accent}; border-color: ${color.accent}; }
`;
