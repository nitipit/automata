// @ts-types="./adaptive-ui.d.ts"
import { tokens } from "./adaptive-ui.js";
const chatCSS = `
  display: flex;
  flex-direction: column;
  width: min(48rem, 100%);
  height: min(48rem, 90dvh);
  min-height: 30rem;
  box-sizing: border-box;
  overflow: hidden;
  border: 1px solid ${tokens.border};
  border-radius: 1.25rem;
  background: ${tokens.surface};
  box-shadow: 0 18px 65px #14283e12;
  font-size: 1.1rem;

  header { padding: 1.4rem 1.6rem; border-bottom: 1px solid ${tokens.border}; }
  h1 { margin: 0; font-size: 1.65rem; }
  .messages {
    display: flex; flex: 1; flex-direction: column; gap: 1rem;
    overflow-y: auto; padding: 1.5rem; min-height: 0;
  }
  .empty { max-width: 28rem; margin: auto; color: ${tokens.status}; text-align: center; }
  .message { max-width: 90%; padding: .8rem 1rem; border-radius: 1rem; background: #f1f5f9; }
  .message[data-role="user"] { align-self: flex-end; background: #e9f0ff; }
  .message strong { display: block; margin-bottom: .3rem; color: ${tokens.mutedText}; font-size: .95rem; }
  .message p { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
  .message pre, .feedback { white-space: pre-wrap; overflow-wrap: anywhere; font-size: .9rem; }
  .feedback { color: ${tokens.danger}; }
  .composer { padding: 1rem 1.5rem 1.4rem; border-top: 1px solid ${tokens.border}; }
  label { display: block; margin-bottom: .4rem; color: ${tokens.mutedText}; font-size: 1rem; }
  textarea {
    width: 100%; min-height: min(5rem, 30vh); max-height: 30vh; box-sizing: border-box;
    resize: none; overflow-y: auto; padding: .7rem;
    border: 1px solid ${tokens.border}; border-radius: .65rem; font: inherit;
  }
  textarea:focus-visible { outline: 2px solid ${tokens.focus}; outline-offset: 2px; }
  .footer { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-top: .6rem; }
  .status { color: ${tokens.status}; font-size: 1rem; }
  aui-button { font-size: inherit; }
  .validation-send[hidden] { display: none; }
  button:disabled { opacity: .45; cursor: not-allowed; }
`;
export {
  chatCSS
};
