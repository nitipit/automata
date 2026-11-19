import type { ResolvedTheme } from "./_theme/index";

export const composerStyle = `
  display: block;
  & p { margin: 0; }
  & #run-status { font-size: .85rem; }
  & #run-status:empty { display: none; }
  & form { padding: 1rem 1.35rem 1.2rem; border-top: 1px solid; }
  & form > label { display: block; font-size: .8rem; font-weight: 700; margin-bottom: .4rem; }
  & textarea { width: 100%; resize: vertical; min-height: 5rem; padding: .7rem .8rem; border: 1px solid; border-radius: .6rem; }
  & .composer-actions { display: flex; justify-content: space-between; margin-top: .65rem; align-items: flex-end; gap: .65rem; }
  & .runtime-controls { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); align-items: end; gap: .6rem; flex: 1 1 auto; min-width: 0; max-width: 22rem; }
  & .runtime-controls { font-size: .85rem; }
  & .composer-hint, & #runtime-controls-status { margin-top: .45rem; font-size: .76rem; overflow-wrap: anywhere; }
  & #runtime-controls-status:empty { display: none; }
  & #send svg { width: 1.15rem; height: 1.15rem; }
  & button { cursor: pointer; border: 1px solid; border-radius: .55rem; padding: .55rem .95rem; font-weight: 650; }
  & button:disabled { opacity: .48; cursor: not-allowed; }
  & #send { display: inline-grid; place-items: center; flex: none; width: 2.75rem; height: 2.75rem; padding: 0; border-radius: 50%; }
`;

export function composerTheme({ roles: r }: ResolvedTheme): string {
  return `
    & textarea, & button { background: ${r.surface}; color: ${r.text}; border-color: ${r.border}; }
    & form { border-color: ${r.border}; }
    & #run-status, & .composer-hint, & #runtime-controls-status { color: ${r.mutedText}; }
    & #send { color: ${r.accentText}; background: ${r.accent}; border-color: ${r.accent}; }
    & :is(textarea, button):focus-visible { outline-color: ${r.focus}; }
  `;
}
