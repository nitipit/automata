import { color } from "./_tokens/color";

/** Adapter scopes these nested rules to the automata-app element. */
export const appStyle = `
  display: block;
  max-width: 1600px;
  margin: auto;
  padding: clamp(1rem, 3vw, 2.5rem);
  & .skip-link { position: absolute; left: -10000px; }
  & .skip-link:focus { position: fixed; left: 1rem; top: 1rem; z-index: 10; background: white; padding: .5rem; }
  & .app-header, & .panel-heading, & .composer-actions { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
  & .app-header { margin-bottom: 1.5rem; }
  & h1, & h2, & p { margin: 0; }
  & h1 { font-size: clamp(1.6rem, 3vw, 2.25rem); letter-spacing: -.04em; line-height: 1.15; }
  & h2 { font-size: 1.15rem; letter-spacing: -.015em; }
  & .eyebrow { color: ${color.muted}; font-size: .68rem; font-weight: 750; letter-spacing: .13em; }
  & .workspace { display: grid; grid-template-columns: minmax(0, 1fr); }
  & .chat-panel { min-width: 0; background: ${color.surface}; border: 1px solid ${color.line}; border-radius: 1.1rem; overflow: hidden; box-shadow: 0 12px 40px #183c2910; }
  & .chat-panel { display: flex; flex-direction: column; min-height: min(72vh, 800px); }
  & .panel-heading { padding: 1.15rem 1.35rem; border-bottom: 1px solid ${color.line}; }
  & #run-status { color: ${color.muted}; font-size: .85rem; }
  & .transcript { flex: 1; display: flex; flex-direction: column; align-items: stretch; gap: 1rem; padding: 1.35rem; overflow-y: auto; max-height: 60vh; }
  & .empty-state { color: ${color.muted}; font-size: .93rem; }
  & .message { max-width: 92%; padding: .8rem 1rem; border-radius: .9rem; background: #f2f6f2; overflow-wrap: anywhere; white-space: pre-wrap; }
  & .message.user { align-self: flex-end; background: ${color.accentSoft}; }
  & .message-label { display: block; color: ${color.muted}; font-size: .72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; margin-bottom: .3rem; }
  & .generated-content { min-width: 0; max-width: 100%; flex-shrink: 0; padding: 1rem; border: 1px solid ${color.line}; border-radius: .9rem; overflow-x: auto; overflow-wrap: anywhere; }
  & .generated-content[hidden] { display: none; }
  & .composer { padding: 1rem 1.35rem 1.2rem; border-top: 1px solid ${color.line}; }
  & .composer label { display: block; font-size: .8rem; font-weight: 700; margin-bottom: .4rem; }
  & textarea { width: 100%; resize: vertical; min-height: 5rem; padding: .7rem .8rem; border: 1px solid #a8beb0; border-radius: .6rem; color: ${color.ink}; background: white; }
  & .composer-actions { margin-top: .65rem; }
  & .composer-actions p { color: ${color.muted}; font-size: .76rem; }
  & .composer-actions > div { display: flex; flex-shrink: 0; }
  & button { cursor: pointer; border: 1px solid ${color.line}; border-radius: .55rem; padding: .55rem .95rem; color: ${color.ink}; background: white; font-weight: 650; }
  & button:disabled { opacity: .48; cursor: not-allowed; }
  & #send { color: white; background: ${color.accent}; border-color: ${color.accent}; margin-left: .4rem; }
  @media (max-width: 760px) {
    & .chat-panel { min-height: 65vh; }
    & .composer-actions { align-items: flex-end; }
    & .composer-actions p { max-width: 10rem; }
  }
`;
