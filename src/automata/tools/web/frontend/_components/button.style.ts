import type { ResolvedTheme } from "../_theme/index";

export const buttonStyle = `
  display: inline-block;
  max-width: 100%;
  & > button {
    box-sizing: border-box;
    max-width: 100%;
    min-height: 2.5rem;
    padding: 0.55rem 0.9rem;
    border: 1px solid transparent;
    border-radius: 0.5rem;
    font: inherit;
    font-weight: 600;
    cursor: pointer;
    overflow-wrap: anywhere;
  }
  & > button:disabled { cursor: not-allowed; opacity: 0.6; }
  & > button:focus-visible { outline: 3px solid; outline-offset: 2px; }
`;

export function buttonTheme(theme: ResolvedTheme): string {
  const { accent, accentText, focus } = theme.roles;
  return `& > button { background: ${accent}; color: ${accentText}; }
    & > button:focus-visible { outline-color: ${focus}; }`;
}
