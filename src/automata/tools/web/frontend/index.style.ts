import type { ResolvedTheme } from "./_theme/index";

/** Structural page styles; color values are resolved per app instance below. */
export const appStyle = `
  display: block;
  max-width: 1600px;
  margin: auto;
  padding: clamp(1rem, 3vw, 2.5rem);
  & .skip-link { position: absolute; left: -10000px; }
  & .skip-link:focus { position: fixed; left: 1rem; top: 1rem; z-index: 10; padding: .5rem; }
  & #sessions-picker button { cursor: pointer; padding: .55rem .85rem; border: 1px solid; border-radius: .55rem; }
  & #sessions-picker { width: min(62rem, calc(100% - 2rem)); height: min(42rem, 91dvh); max-height: 91dvh; padding: 0; border: 1px solid; border-radius: 1.05rem; overflow: hidden; box-shadow: 0 24px 80px #0004; }
  & #sessions-picker[open] { display: flex; flex-direction: column; }
  & #sessions-picker::backdrop { background: #0008; }
  & .sessions-header { display: flex; align-items: center; justify-content: space-between; gap: .7rem; padding: .85rem 1.25rem; border-bottom: 1px solid; }
  & #sessions-heading { margin: .1rem 0 0; font-size: clamp(1.15rem, 3vw, 1.45rem); line-height: 1.2; }
  & #sessions-picker p { overflow-wrap: anywhere; }
  & #sessions-status { margin: 0; padding: .55rem 1.25rem; font-size: .85rem; border-bottom: 1px solid; }
  & #sessions-status:empty, & #sessions-list:empty, & #sessions-back { display: none; }
  & .sessions-layout { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 3fr); }
  & .sessions-directory, & #sessions-preview-scroll { min-width: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
  & .sessions-directory { padding: .85rem; border-inline-end: 1px solid; }
  & #sessions-list { list-style: none; display: grid; grid-template-columns: minmax(0, 1fr); gap: .35rem; margin: 0; padding: 0; }
  & #new-chat { width: 100%; min-height: 44px; margin-bottom: .6rem; font-weight: 650; }
  & #sessions-list li { min-width: 0; }
  & #sessions-list button { width: 100%; max-width: 100%; text-align: start; line-height: 1.3; padding: .65rem .75rem; }
  & .sessions-row-title { display: flex; justify-content: space-between; align-items: baseline; gap: .65rem; }
  & .sessions-row-title strong, & #sessions-list small { display: block; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  & #sessions-list time { flex: none; font-size: .72rem; }
  & #sessions-list small { margin-top: .25rem; font-size: .79rem; }
  & #sessions-picker button:disabled { opacity: .58; cursor: not-allowed; }
  & .sessions-actions { display: flex; gap: .4rem; flex-wrap: wrap; justify-content: end; }
  & .sessions-directory .sessions-actions { margin-top: .7rem; }
  & .sessions-preview { display: flex; flex-direction: column; min-width: 0; min-height: 0; overflow-wrap: anywhere; --preview-pad: clamp(1rem, 3vw, 1.75rem); }
  & #sessions-placeholder { padding: var(--preview-pad); margin: min(4dvh, 2rem) 0; }
  & #sessions-detail:not([hidden]) { flex: 1; min-height: 0; display: grid; grid-template-rows: minmax(0, 1fr) auto; }
  & #sessions-preview-scroll { padding: var(--preview-pad); }
  & .sessions-preview h3 { font-size: 1.4rem; line-height: 1.2; margin: .25rem 0 .75rem; }
  & .sessions-preview h4 { font-size: .9rem; margin: 1.2rem 0 .55rem; }
  & #sessions-preview-status { font-size: .84rem; margin: .4rem 0 .8rem; }
  & #sessions-preview-status[data-ready] { position: absolute; inline-size: 1px; block-size: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; margin: 0; }
  & .sessions-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .8rem 1rem; margin: 0; padding: .85rem; border: 1px solid; border-radius: .65rem; }
  & .sessions-facts dt, & .sessions-turn strong { font-size: .76rem; font-weight: 650; }
  & .sessions-facts dd { margin: .15rem 0 0; font-size: .87rem; }
  & .sessions-turn { padding: .65rem .8rem; margin-bottom: .45rem; border-radius: .65rem; }
  & .sessions-turn p { margin: .2rem 0 0; font-size: .9rem; white-space: pre-wrap; }
  & #sessions-opening { padding: .7rem var(--preview-pad) .9rem; border-top: 1px solid; }
  & #sessions-caution { font-size: .8rem; margin: 0 0 .55rem; }
  & #sessions-open { min-height: 44px; font-weight: 650; }
  @media (max-width: 680px) {
    & #sessions-picker { width: calc(100% - 1rem); height: 95dvh; max-height: 95dvh; border-radius: .85rem; }
    & .sessions-header, & #sessions-status { padding-inline: .85rem; }
    & .sessions-header button { padding-inline: .6rem; }
    & .sessions-layout { grid-template-columns: minmax(0, 1fr); }
    & .sessions-directory { border-inline-end: 0; }
    & #sessions-picker:not([data-detail]) .sessions-preview, & #sessions-picker[data-detail] .sessions-directory { display: none; }
    & #sessions-back { display: inline-block; align-self: start; min-height: 44px; margin: .8rem var(--preview-pad) 0; }
    & #sessions-open { width: 100%; }
  }
  @media (max-height: 430px) {
    & .sessions-preview { overflow-y: auto; }
    & #sessions-detail:not([hidden]) { display: block; }
    & #sessions-preview-scroll { overflow-y: visible; }
  }
  & .eyebrow { font-size: .68rem; font-weight: 750; letter-spacing: .13em; }
  & .workspace { display: grid; grid-template-columns: minmax(0, 1fr); }
  & .chat-panel { min-width: 0; border: 1px solid; border-radius: 1.1rem; overflow: hidden; box-shadow: 0 12px 40px #183c2910; display: flex; flex-direction: column; min-height: min(72vh, 800px); }
  & #messages { flex: 1; display: flex; flex-direction: column; align-items: stretch; gap: 1rem; padding: 1.35rem; overflow-y: auto; max-height: 60vh; }
  & .empty-state { font-size: .93rem; }
  & #messages > .inactive-ui { margin-top: .7rem; font-size: .85rem; }
  @media (max-width: 760px) {
    & .chat-panel { min-height: 65vh; }
  }
`;
export function appThemeStyle({ mode, roles: r }: ResolvedTheme): string {
  return `
    color: ${r.text}; color-scheme: ${mode};
    & .skip-link:focus, & .chat-panel { background: ${r.surface}; color: ${r.text}; }
    & .eyebrow, & .empty-state, & #messages > .inactive-ui { color: ${r.mutedText}; }
    & .chat-panel { border-color: ${r.border}; }
    & #sessions-picker, & #sessions-picker button { background: ${r.surface}; color: ${r.text}; border-color: ${r.border}; }
    & .sessions-directory, & .sessions-facts, & .sessions-turn { background: ${r.surfaceRaised}; }
    & .sessions-header, & .sessions-directory, & .sessions-facts, & #sessions-status, & #sessions-opening { border-color: ${r.border}; }
    & #sessions-list button:not(:disabled):hover { border-color: ${r.accent}; }
    & #sessions-list button[aria-pressed="true"] { background: ${r.accentSoft}; border-color: ${r.accent}; }
    & #sessions-open:not(:disabled) { color: ${r.accentText}; background: ${r.accent}; border-color: ${r.accent}; }
    & #sessions-list small, & #sessions-list time, & #sessions-status, & #sessions-preview-status, & .sessions-facts dt, & .sessions-turn strong, & #sessions-caution, & #sessions-placeholder p { color: ${r.mutedText}; }
    & #sessions-picker :focus-visible, & .skip-link:focus-visible { outline-color: ${r.focus}; }
  `;
}
