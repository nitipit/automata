import type { ResolvedTheme } from "./_theme/index";

export const sessionControlsStyle = `
  display: block;
  min-width: 0;
  & .session-row { display: flex; flex-wrap: wrap; align-items: center; gap: .35rem .75rem; padding: .55rem 1.35rem; border-top: 1px solid; }
  & .session-identity { min-width: 0; flex: 1 1 13rem; overflow-wrap: anywhere; }
  & .session-title { position: relative; display: flex; align-items: center; gap: .35rem; }
  & .session-title h1 { margin: 0; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  & .session-title :is(h1, input) { font-size: 1.125rem; font-weight: 700; line-height: 1.2; }
  & .session-title:has(#rename:not(:disabled)) h1 { cursor: text; }
  & .session-title[data-editing] > :is(h1, button) { visibility: hidden; }
  & button { min-height: 44px; cursor: pointer; padding: .35rem .65rem; border: 1px solid; border-radius: .55rem; font-size: .85rem; }
  & button:disabled { opacity: .5; cursor: not-allowed; }
  & #rename { flex: 0 0 44px; width: 44px; padding: 0; display: grid; place-items: center; border-color: transparent; background: transparent; }
  & #rename svg { width: 16px; height: 16px; }
  & #rename-form { position: absolute; inset: 0; }
  & #rename-form input { display: block; width: 100%; height: 100%; padding: 0 .35rem; border: 1px solid; border-radius: .55rem; }
  & .session-actions, & .session-connection { display: flex; flex-wrap: wrap; align-items: center; gap: .35rem .5rem; min-width: 0; }
  & .session-connection:has(#connection-detail:not(:empty)) { flex: 1 1 100%; }
  & #connection-detail { flex: 1 1 100%; overflow-wrap: anywhere; }
  & :is(#connection-detail, #rename-error) { margin: 0; }
  & :is(#connection-detail, #rename-error):empty { display: none; }
  & :is(#connection-status, #connection-detail, #rename-error) { font-size: .85rem; }
  @media (max-width: 600px) {
    & .session-identity { flex-basis: 100%; }
  }
`;

export function sessionControlsTheme({ roles: r }: ResolvedTheme): string {
  return `
    & button, & #rename-form input { background: ${r.surface}; color: ${r.text}; border-color: ${r.border}; }
    & .session-row { border-color: ${r.border}; }
    & #rename:not(:disabled):hover { background: ${r.surfaceRaised}; }
    & :is(#connection-status, #connection-detail, #rename-error) { color: ${r.mutedText}; }
    & :is(button, input):focus-visible { outline-color: ${r.focus}; }
  `;
}
