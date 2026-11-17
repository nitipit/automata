import type { ResolvedTheme } from "./_theme/index";

/** Structural page styles; color values are resolved per app instance below. */
export const appStyle = `
  display: block;
  max-width: 1600px;
  margin: auto;
  padding: clamp(1rem, 3vw, 2.5rem);
  & .skip-link { position: absolute; left: -10000px; }
  & .skip-link:focus { position: fixed; left: 1rem; top: 1rem; z-index: 10; padding: .5rem; }
  & .app-header, & .composer-actions { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
  & .app-header { margin-bottom: 1.5rem; flex-wrap: wrap; }
  & .session-identity { min-width: 0; flex: 1 1 16rem; overflow-wrap: anywhere; }
  & .session-title { display: flex; align-items: center; gap: .35rem; }
  & .session-title h1 { min-width: 0; }
  & #rename { flex: 0 0 44px; width: 44px; height: 44px; padding: 0; display: grid; place-items: center; }
  & #rename svg { width: 20px; height: 20px; }
  & .connection-controls { display: flex; align-items: center; gap: .5rem; font-size: .85rem; }
  & #connect[hidden] { display: none; }
  & .app-header button:disabled { opacity: .5; cursor: not-allowed; }
  & #rename-form { flex: 1 1 100%; min-width: 0; }
  & #rename-form[hidden], & #rename[hidden] { display: none; }
  & #rename-form input { display: block; width: 100%; margin: .4rem 0; padding: .6rem; border: 1px solid; border-radius: .55rem; }
  & .app-header button { cursor: pointer; padding: .55rem .85rem; border: 1px solid; border-radius: .55rem; }
  & #rename-form button + button { margin-left: .4rem; }
  & #rename-error:empty, & #run-status:empty, & #connection-detail:empty { display: none; }
  & .reply-activity, & .reply-outcome { font-size: .85rem; margin: .5rem 0 0; }
  & .app-header h1, & .composer p { margin: 0; }
  & .app-header h1 { font-size: clamp(1.6rem, 3vw, 2.25rem); letter-spacing: -.04em; line-height: 1.15; }
  & .eyebrow { font-size: .68rem; font-weight: 750; letter-spacing: .13em; }
  & .workspace { display: grid; grid-template-columns: minmax(0, 1fr); }
  & .chat-panel { min-width: 0; border: 1px solid; border-radius: 1.1rem; overflow: hidden; box-shadow: 0 12px 40px #183c2910; display: flex; flex-direction: column; min-height: min(72vh, 800px); }
  & #run-status { font-size: .85rem; }
  & .transcript { flex: 1; display: flex; flex-direction: column; align-items: stretch; gap: 1rem; padding: 1.35rem; overflow-y: auto; max-height: 60vh; }
  & .empty-state { font-size: .93rem; }
  & .message { max-width: 92%; padding: .8rem 1rem; border-radius: .9rem; overflow-wrap: anywhere; white-space: pre-wrap; }
  & .message-body { white-space: normal; }
  & .message.user { align-self: flex-end; }
  & .message.user .message-body { white-space: pre-wrap; }
  & .message-label { display: block; font-size: .72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; margin-bottom: .3rem; }
  & .generated-content { min-width: 0; max-width: 100%; margin-top: .7rem; padding: 1rem; border: 1px solid; border-radius: .9rem; overflow-x: auto; overflow-wrap: anywhere; white-space: normal; }
  & .inactive-ui { margin-top: .7rem; font-size: .85rem; }
  & .composer { padding: 1rem 1.35rem 1.2rem; border-top: 1px solid; }
  & .composer label { display: block; font-size: .8rem; font-weight: 700; margin-bottom: .4rem; }
  & .composer textarea { width: 100%; resize: vertical; min-height: 5rem; padding: .7rem .8rem; border: 1px solid; border-radius: .6rem; }
  & .composer-actions { margin-top: .65rem; }
  & .composer-actions p { font-size: .76rem; }
  & .composer-actions > div { display: flex; flex-shrink: 0; }
  & .composer button { cursor: pointer; border: 1px solid; border-radius: .55rem; padding: .55rem .95rem; font-weight: 650; }
  & .composer button:disabled { opacity: .48; cursor: not-allowed; }
  & #send { margin-left: .4rem; }
  @media (max-width: 760px) {
    & .chat-panel { min-height: 65vh; }
    & .composer-actions { align-items: flex-end; }
    & .composer-actions p { max-width: 10rem; }
  }
`;
export function appThemeStyle({ mode, roles: r }: ResolvedTheme): string {
  return `
    color: ${r.text}; color-scheme: ${mode};
    & .skip-link:focus, & .chat-panel, & .composer textarea, & .composer button, & .app-header button, & #rename-form input { background: ${r.surface}; color: ${r.text}; }
    & .eyebrow, & #run-status, & #connection-status, & #connection-detail, & .reply-activity, & .empty-state, & .message-label, & .inactive-ui, & .composer-actions p { color: ${r.mutedText}; }
    & .chat-panel, & .generated-content, & .composer, & .composer textarea, & .composer button, & .app-header button, & #rename-form input { border-color: ${r.border}; }
    & .message { background: ${r.surfaceRaised}; }
    & .message.user { background: ${r.accentSoft}; }
    & #send { color: ${r.accentText}; background: ${r.accent}; border-color: ${r.accent}; }
    & #rename-error, & .reply-outcome { color: ${r.mutedText}; }
    & .app-header :focus-visible, & .composer :focus-visible, & .skip-link:focus-visible { outline-color: ${r.focus}; }
  `;
}
