import type { ResolvedTheme } from "../_theme/index";

export const selectStyle = `
  display: grid;
  min-width: 0;
  gap: .2rem;
  & > label { font-weight: 600; }
  & > label:empty { display: none; }
  & > select {
    box-sizing: border-box;
    display: block;
    width: 100%;
    min-width: 0;
    min-height: 2.75rem;
    padding: .3rem;
    border: 1px solid;
    border-radius: .55rem;
    font: inherit;
    text-overflow: ellipsis;
  }
  & > select:focus-visible { outline: 3px solid; outline-offset: 2px; }
  & > select:disabled { opacity: .65; cursor: not-allowed; }
`;

export function selectTheme({ roles: { surface, text, border, focus } }: ResolvedTheme): string {
  return `& > select { color: ${text}; background: ${surface}; border-color: ${border}; }
    & > select:focus-visible { outline-color: ${focus}; }`;
}
